from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
import logging
from functools import wraps
from datetime import datetime

from app.models.performance_aegis import get_balance_aegis
from app.models.users import get_users_registered
from app.models.transaction_wallet import get_deposits_pending, get_withdrawals_pending
from app.viewmodels.wallet.found import WalletAdmin

admin_bp = Blueprint('admin', __name__)
logger = logging.getLogger(__name__)

wallet = WalletAdmin()

def admin_required(f):
    """Decorator to check if the current user is an admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(404)  # Unauthorized
        if current_user.role != "admin":
            abort(404)  # Forbidden - not admin
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route("/admin/panel")
@login_required
@admin_required
def admin_route():
    """Admin panel page route"""
    tx = wallet.get_list_founds(page=1)
    
    # Balances are now loaded dynamically via JavaScript
    return render_template("admin/panel.html", transations=tx, is_admin=(current_user.role == "admin"))

@admin_bp.route("/admin/verify-transaction", methods=["POST"])
@login_required
@admin_required
def admin_verify_transaction():
    """Admin verify transaction route"""
    data = request.get_json()
    id = data.get("transaction_id")

    data = wallet.get_data_with_id(id)

    if data.verification:
        return jsonify({"success": False, "error": "the transaction has been verified before"})

    is_valid = wallet.set_verification(id, True)

    if data:
        wallet.add_found(data.user_id, data.amount, data.currency, "general")
    return jsonify({"success": is_valid})

@admin_bp.route("/admin/process-withdrawal", methods=["POST"])
@login_required
@admin_required
def admin_process_withdrawal():
    """Admin process withdrawal route"""
    data = request.get_json()
    id = data.get("transaction_id")
    tx_hash = data.get("tx_hash")

    if not tx_hash:
        return jsonify({"success": False, "message": "Transaction hash is required"})

    # Mark as verified and store the TX hash
    is_valid = wallet.set_verification_with_tx_hash(id, True, tx_hash)
    
    return jsonify({"success": is_valid})

@admin_bp.route("/admin/real-balances", methods=["GET"])
@login_required
@admin_required
def get_real_master_balances():
    """Get real master account balances from exchange APIs"""
    try:
        real_balances = wallet.get_real_master_account_balances()
        return jsonify({
            "success": True,
            "data": real_balances,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting real master balances: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@admin_bp.route("/admin/general-info", methods=["POST"])
@login_required
@admin_required
def get_general_info():
    aegis_balance = get_balance_aegis()
    users_registered = get_users_registered()
    deposits_pending = get_deposits_pending()
    withdrawals_pending = get_withdrawals_pending()

    return jsonify({
        "success": True,
        "data": {
            "aegis_balance": aegis_balance,
            "users_registered": users_registered,
            "deposits_pending": deposits_pending,
            "withdrawals_pending": withdrawals_pending
        },
        "timestamp": datetime.now().isoformat()
    })

@admin_bp.route("/admin/real-balances-summary", methods=["GET"])
@login_required
@admin_required
def get_real_master_balance_summary():
    """Get summary of real master account balances with USDT totals"""
    try:
        summary = wallet.get_real_master_balance_summary()
        return jsonify({
            "success": True,
            "data": summary,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting real master balance summary: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@admin_bp.route("/admin/refresh-balances", methods=["POST"])
@login_required
@admin_required
def refresh_real_balances():
    """Force refresh of real master account balances"""
    try:
        # Get both detailed balances and summary
        real_balances = wallet.get_real_master_account_balances()
        summary = wallet.get_real_master_balance_summary()
        
        return jsonify({
            "success": True,
            "detailed_balances": real_balances,
            "summary": summary,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error refreshing real balances: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
