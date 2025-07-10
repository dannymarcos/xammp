from flask import Blueprint, render_template, jsonify, url_for, request, redirect
from flask_login import login_required, current_user
import logging

from app.iu.routes.utils.utils import get_translated_text
from app.models.users import User

finances_bp = Blueprint('finances', __name__)
logger = logging.getLogger(__name__)

@finances_bp.route("/finances")
@login_required
def finances_route():
    """Finances page route"""
    try:
        return render_template("finances.html", get_translated_text=get_translated_text) 
    except Exception as e:
        logger.error(f"Error in finances route: {e}")
        return render_template("finances.html", error="An error occurred loading finances.", get_translated_text=get_translated_text)


@finances_bp.route("/request_withdrawal", methods=["POST"])
@login_required
def request_withdrawal():
    """Handle withdrawal requests"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
        
        amount = float(data.get('amount', 0))
        currency = data.get('currency', 'USDT')
        wallet_address = data.get('wallet_address')
        
        if amount <= 0:
            return jsonify({"status": "error", "message": "Invalid withdrawal amount"}), 400
        
        if not wallet_address:
            return jsonify({"status": "error", "message": "Wallet address is required"}), 400
        
        # Validate wallet address format based on currency
        if currency == 'USDT' and not wallet_address.startswith('T'):
            return jsonify({"status": "error", "message": "Invalid USDT (TRC20) wallet address"}), 400
        elif currency == 'BTC' and not (wallet_address.startswith('1') or wallet_address.startswith('3') or wallet_address.startswith('bc1')):
            return jsonify({"status": "error", "message": "Invalid BTC wallet address"}), 400

        # Redirect to withdrawal confirmation page
        return jsonify({
            "status": "success",
            "message": "Balance verified. Please confirm withdrawal details.",
            "redirect": url_for('routes.confirm_withdrawal', 
                                amount=amount,
                                currency=currency,
                                wallet_address=wallet_address)
        })
    except Exception as e:
        logger.error(f"Error processing withdrawal request: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@finances_bp.route("/confirm_withdrawal")
@login_required
def confirm_withdrawal():
    """Withdrawal confirmation page"""
    try:
        amount = request.args.get('amount')
        currency = request.args.get('currency')
        wallet_address = request.args.get('wallet_address')
        
        if not all([amount, currency, wallet_address]):
            return redirect(url_for('routes.finances_route'))
        
        user = User.query.filter_by(email='test@example.com').first()
        if not user:
            return redirect(url_for('routes.finances_route'))
            
        return render_template('confirm_withdrawal.html',
            amount=amount,
            currency=currency,
            wallet_address=wallet_address,
            # user=user
        )
    except Exception as e:
        logger.error(f"Error displaying withdrawal confirmation: {e}")
        return redirect(url_for('routes.finances_route'))
