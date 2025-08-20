from flask import Blueprint, redirect, render_template, request, jsonify, url_for
from flask_login import login_required, current_user
from app.iu.routes.utils.utils import get_translated_text
from app.models.users import get_referred_by_user
from app.viewmodels.wallet.found import Wallet, WalletAdmin
from app.models.transaction_wallet import FoundWallet
from datetime import datetime, timezone
import logging

wallet_bp = Blueprint('wallet', __name__)
logger = logging.getLogger(__name__)

def is_float(text):
    try:
        float(text)

        return True
    except ValueError:
        return False

def get_last_verified_deposit_or_withdrawal(user_id):
    """
    Devuelve la fecha del último depósito o retiro verificado del usuario.
    """
    last_tx = (
        FoundWallet.query.filter(
            FoundWallet.user_id == user_id,
            FoundWallet.verification == True,
            FoundWallet.transaction_type.in_(["deposit", "withdrawal"])
        )
        .order_by(FoundWallet.time.desc())
        .first()
    )
    return last_tx.time if last_tx else None

def withdrawal_period_active(last_verified):
    disabled_withdraw = False
    days_since = None

    if last_verified:
        now = datetime.now(timezone.utc)

        if last_verified.tzinfo is None:
            last_verified_utc = last_verified.replace(tzinfo=timezone.utc)
        else:
            last_verified_utc = last_verified.astimezone(timezone.utc)

        days_since = (now - last_verified_utc).days

        if days_since < 15:
            disabled_withdraw = True
        
    return disabled_withdraw, days_since

@wallet_bp.route("/wallet", methods=['GET', 'POST'])
@login_required
def home_wallet():
    name = current_user.full_name
    id = current_user.id

    wallet = Wallet(id)
    balance = wallet.get_balance()  # Get only general wallet balance
    balance_general = wallet.get_balance("general")  # Get only general wallet balance
    
    # Calculate performance metrics
    performance = wallet.get_accumulated_performance("USDT")
    initial_capital = wallet.get_initial_capital("USDT")

    # Calculate pending balance (transactions with verification=False)
    pending_balance = wallet.get_pending_balance("USDT")
    
    # Calculate pending withdrawal balance
    pending_withdrawal_balance = wallet.get_pending_withdrawal_balance("USDT")
    
    last_verified = get_last_verified_deposit_or_withdrawal(id)
    disabled_withdraw, _ = withdrawal_period_active(last_verified)
    balance_blocked = wallet.get_balance_blocked_usdt()
    print(f"last_verified: {disabled_withdraw}")

    if request.method == 'GET':
        return render_template("wallet.html", 
                                name=name, 
                                balance=balance,
                                balance_general=balance_general,
                                performance=performance,
                                initial_capital=initial_capital,
                                pending_balance=pending_balance,
                                pending_withdrawal_balance=pending_withdrawal_balance,
                                balance_blocked=balance_blocked,
                                disabled_withdraw=disabled_withdraw,
                                is_admin=(current_user.role == "admin"))
    return render_template("under_construction.html")

@wallet_bp.route("/settings/wallet", methods=["GET", "POST"])
@login_required
def settings_wallet_route():
    try:
        return render_template("settings/wallet.html", user=current_user, get_translated_text=get_translated_text)
    except Exception as e:
        logger.error(f"Error in wallet settings: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@wallet_bp.route("/add_found_wallet", methods=["POST"])
@login_required
def add_found_wallets():
    user_id = current_user.id
    amount = request.form.get("amount")
    symbol = "USDT"
    ref = request.form.get("ref")
    red = "BEP-20" # request.form.get("red")

    wallet = Wallet(user_id)
    pending_balance = wallet.get_pending_balance("USDT")
    if pending_balance > 0:
        return jsonify({"success": False, "error": "Pending balance is greater than 0", "pending_balance": pending_balance})

    if amount is None:
        return jsonify({"success": False, "error": "Amount is required"})
    
    if not is_float(amount):
        return jsonify({"success": False, "error": "Amount must be a number"})
    
    if float(amount) <= 0:
        return jsonify({"success": False, "error": "Amount must be greater than 0"})

    if ref is None:
        return jsonify({"success": False, "error": "Reference is required"})

    wallet = Wallet(user_id)
    result = wallet.deposit_found_wallet(float(amount), symbol, ref, red, "general")

    if not result:
        return jsonify({"success": False, "error": "not save in db"})

    return jsonify({"success": True})


@wallet_bp.route("/withdrawal_request", methods=["POST"])
@login_required
def withdrawal_request():
    """Create a withdrawal request with commission system"""
    user_id = current_user.id
    amount = request.form.get("amount")
    symbol = request.form.get("symbol", "USDT")
    ref = request.form.get("ref")  # Wallet address or reference
    red = "BEP-20"

    last_verified = get_last_verified_deposit_or_withdrawal(user_id)
    disabled_withdraw, days_since = withdrawal_period_active(last_verified)

    if disabled_withdraw and days_since is not None:
        return jsonify({
            "success": False,
            "error": f"Withdrawals are only allowed 15 days after your last deposit or withdrawal. Please wait {15 - days_since} more day(s).",
            "withdrawal_locked": True,
            "days_remaining": 15 - days_since
        })

    if not amount:
        return jsonify({"success": False, "error": "Amount is required"})
    
    try:
        amount = float(amount)
        if amount <= 0:
            return jsonify({"success": False, "error": "Amount must be greater than 0"})
        if amount < 10:
            return jsonify({"success": False, "error": "Amount min is 10 USDT"})
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid amount format"})
    
    if not ref:
        return jsonify({"success": False, "error": "Reference is required"})

    wallet = Wallet(user_id)
    admin_wallet = WalletAdmin()

    current_balance = wallet.get_balance_by_currency(symbol, "general")
    if current_balance is None or current_balance < amount:
        return jsonify({"success": False, "error": f"Insufficient balance. Available: {current_balance or 0} {symbol}"})

    if wallet.get_pending_withdrawals():
        return jsonify({"success": False, "error": "You have pending withdrawal requests"})

    try:
        available_gain, amount_total_now, balances_dict = wallet.get_real_performance()
    except Exception as e:
        print(f"Error calculating performance: {e}")
        return jsonify({"success": False, "error": "Error calculating account performance"})
    
    referred_by_user = get_referred_by_user(user_id)

    # Calcular parte de ganancia y parte de capital en el retiro
    # Si hay pérdidas (available_gain < 0), toda la cantidad es capital
    if available_gain < 0:
        gain_part = 0
        capital_part = amount
    else:
        gain_part = min(amount, available_gain)
        capital_part = amount - gain_part

    platform_comision = gain_part * 0.15
    ref_comision = gain_part * 0.05 if referred_by_user else 0.0
    total_comision = platform_comision + ref_comision

    net_amount = amount - total_comision

    try:
        result = wallet.withdrawal_found_wallet(
            amount=net_amount, 
            currency=symbol, 
            ref=ref, 
            red=red, 
            exchange="general", 
            x=False,
            verification=False,
            capital_part=capital_part
        )
    except Exception as e:
        print(f"Error creating withdrawal: {e}")
        return jsonify({"success": False, "error": "Failed to create withdrawal request"})
    
    # Registrar movimiento en fondos
    try:
        admin_wallet.add_found(user_id, -amount, symbol, "general")
    except Exception as e:
        print(f"Error updating funds: {e}")
        # Revertir el retiro si falla la actualización de fondos
        db.session.rollback()
        return jsonify({"success": False, "error": "Failed to update funds"})

    # Registrar comisiones solo si hay ganancias
    if platform_comision > 0:
        try:
            admin_wallet.update_performance_aegis(platform_comision)
        except Exception as e:
            print(f"Error updating platform commission: {e}")
    
    if ref_comision > 0 and referred_by_user:
        try:
            admin_wallet.add_referral_earning(referred_by_user.id, user_id, ref_comision)
            admin_wallet.add_found(referred_by_user.id, ref_comision, symbol, "general")
        except Exception as e:
            print(f"Error adding referral commission: {e}")

    if not result:
        return jsonify({"success": False, "error": "Failed to create withdrawal request"})

    return jsonify({"success": True, "message": "Withdrawal request created successfully"})

@wallet_bp.route("/get_found_wallets", methods=["GET"])
@login_required
def get_found_wallets():
    user_id = current_user.id
    wallet = Wallet(user_id)
    founds = wallet.get_found_wallets()
    return jsonify({"success": True, "founds": founds})

@wallet_bp.route("/get_transaction_history", methods=["GET"])
@login_required
def get_transaction_history():
    """Get user's complete transaction history (deposits and withdrawals) with status and TX hash"""
    user_id = current_user.id
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    try:
        pagination = FoundWallet.query.filter_by(
            user_id=user_id,
            x=False
        ).order_by(FoundWallet.time.desc()).paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        transaction_history = []
        for transaction in pagination.items:
            # Determine status based on transaction type and verification
            if transaction.transaction_type == "withdrawal":
                status = "Processed" if transaction.verification else "Pending"
            else:  # deposit
                status = "Verified" if transaction.verification else "Pending"
            
            transaction_data = {
                "id": transaction.id,
                "type": transaction.transaction_type,
                "amount": transaction.amount,
                "currency": transaction.currency,
                "network": transaction.red,
                "reference": transaction.ref,  # Transaction ID for deposits, wallet address for withdrawals
                "time": transaction.time.isoformat() if transaction.time else None,
                "status": status,
                "tx_hash": transaction.tx_hash if transaction.tx_hash else None,
                "formatted_time": transaction.time.strftime('%Y-%m-%d %H:%M:%S') if transaction.time else 'N/A'
            }
            transaction_history.append(transaction_data)
        
        return jsonify({
            "success": True, 
            "transactions": transaction_history,
            "pagination": {
                "current_page": page,
                "per_page": per_page,
                "total_pages": pagination.pages,
                "total_items": pagination.total,
                "has_prev": pagination.has_prev,
                "has_next": pagination.has_next,
                "prev_num": pagination.prev_num,
                "next_num": pagination.next_num
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting transaction history: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@wallet_bp.route("/api/wallet/chart-data", methods=["GET"])
@login_required
def get_wallet_chart_data():
    """
    Get chart data for wallet earnings/losses over time
    Returns JSON with labels and datasets for Chart.js
    """
    try:
        user_id = current_user.id
        wallet = Wallet(user_id)
        
        # Get chart data from wallet class
        chart_data_raw = wallet.get_chart_data(days=1)
        
        # Format data for Chart.js
        chart_data = {
            "labels": chart_data_raw["labels"],
            "datasets": [
                {
                    "label": "Ganancias",
                    "data": chart_data_raw["earnings_data"],
                    "borderColor": "rgb(75, 192, 192)",
                    "backgroundColor": "rgba(75, 192, 192, 0.2)",
                    "borderWidth": 2,
                    "tension": 0.1
                },
                {
                    "label": "Pérdidas",
                    "data": chart_data_raw["losses_data"],
                    "borderColor": "rgb(255, 99, 132)",
                    "backgroundColor": "rgba(255, 99, 132, 0.2)",
                    "borderWidth": 2,
                    "tension": 0.1
                }
            ]
        }
        
        return jsonify({
            "success": True,
            "data": chart_data
        })
        
    except Exception as e:
        logger.error(f"Error getting wallet chart data: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@wallet_bp.route("/api/wallet/performance-summary", methods=["GET"])
@login_required
def get_performance_summary():
    """
    Get detailed performance summary including realized and unrealized P&L
    Returns JSON with comprehensive performance data
    """
    try:
        user_id = current_user.id
        wallet = Wallet(user_id)
        
        # Get all performance metrics
        trading_performance = wallet.get_accumulated_performance("USDT")
        real_performance = wallet.get_real_performance("USDT")
        open_positions_pnl = wallet.get_open_positions_pnl("USDT")
        
        # Calculate total performance including unrealized
        total_realized = trading_performance["net_performance"]
        total_unrealized = open_positions_pnl["total_unrealized"]
        total_performance = total_realized + total_unrealized
        
        # Calculate total performance percentage
        total_deposits = real_performance["total_deposits"]
        total_performance_percentage = 0
        if total_deposits > 0:
            total_performance_percentage = (total_performance / total_deposits) * 100
        
        summary = {
            "trading_performance": trading_performance,
            "real_performance": real_performance,
            "open_positions": open_positions_pnl,
            "total_performance": {
                "realized": total_realized,
                "unrealized": total_unrealized,
                "total": total_performance,
                "percentage": total_performance_percentage
            }
        }
        
        return jsonify({
            "success": True,
            "data": summary
        })
        
    except Exception as e:
        logger.error(f"Error getting performance summary: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@wallet_bp.route("/api/wallet/period-performance", methods=["GET"])
@login_required
def get_period_performance():
    """
    Get performance data for different periods (daily, weekly, monthly)
    Returns JSON with period performance data
    """
    try:
        user_id = current_user.id
        wallet = Wallet(user_id)
        period = request.args.get('period', 'daily')  # daily, weekly, monthly
        
        # Validate period parameter
        if period not in ['daily', 'weekly', 'monthly']:
            period = 'daily'
        
        # Get period performance
        period_data = wallet.get_period_performance(period, "USDT")
        
        return jsonify({
            "success": True,
            "data": period_data
        })
        
    except Exception as e:
        logger.error(f"Error getting period performance: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500