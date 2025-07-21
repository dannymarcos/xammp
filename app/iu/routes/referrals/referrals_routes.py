from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from app.models.referral_link import ReferralLink
from app.models.users import User, get_user_referrals
from app.models.referral_earnings import ReferralEarnings, get_total_referral_earnings
from app.Aplicacion import db
from datetime import datetime, timedelta
import logging
import uuid

referrals_bp = Blueprint('referrals', __name__)
logger = logging.getLogger(__name__)

@referrals_bp.route("/referrals", methods=['GET', 'POST'])
@login_required
def referrals():
    if request.method == 'GET':
        user = User.query.filter_by(id=current_user.id).first()
        if not user:
            return render_template("referrals.html", is_admin=(current_user.role == "admin"))

        total_earnings = get_total_referral_earnings(user.id)
        
        direct_referrals = get_user_referrals(user.id)
        total_users_invited = len(direct_referrals)
        
        return render_template("referrals.html", 
                             is_admin=(current_user.role == "admin"),
                             total_earnings=total_earnings,
                             total_users_invited=total_users_invited)
    return render_template("under_construction.html")

@referrals_bp.route("/get_referral_link", methods=["GET"])
@login_required
def get_referral_link():
    try:
        user = User.query.filter_by(id=current_user.id).first()
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404
        
        referral_code = user.id
        
        base_url = request.host_url.rstrip('/')
        referral_url = f"{base_url}/register?ref={referral_code}"
        
        return jsonify({
            "status": "success",
            "referral_url": referral_url,
        })
    except Exception as e:
        logger.error(f"Error getting referral link: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@referrals_bp.route("/get_referral_stats", methods=["GET"])
@login_required
def get_referral_stats():
    """Get referral statistics for the current user"""
    try:
        user = User.query.filter_by(id=current_user.id).first()
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404
        
        # Get direct referrals (users who registered using this user's referral link)
        direct_referrals = User.query.filter_by(referred_by=user.id).all()
        
        # Get referral links created by this user
        referral_links = ReferralLink.query.filter_by(user_id=user.id).all()
        
        # Calculate statistics
        total_referrals = len(direct_referrals)
        active_links = len([link for link in referral_links if link.active])
        used_links = len([link for link in referral_links if not link.active])
        
        # Get referral details
        referral_details = []
        for referral in direct_referrals:
            referral_details.append({
                "id": referral.id,
                "name": referral.full_name,
                "email": referral.email,
                "registration_date": referral.id  # Using ID as proxy for registration date
            })
        
        return jsonify({
            "status": "success",
            "total_referrals": total_referrals,
            "active_links": active_links,
            "used_links": used_links,
            "referrals": referral_details
        })
        
    except Exception as e:
        logger.error(f"Error getting referral stats: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@referrals_bp.route("/get_referral_friends", methods=["GET"])
@login_required
def get_referral_friends():
    """Get referral friends table data"""
    try:
        user = User.query.filter_by(id=current_user.id).first()
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404

        direct_referrals = User.query.filter_by(referred_by=user.id).all()
        
        referral_friends = []
        for referral in direct_referrals:
            earnings = ReferralEarnings.query.filter_by(
                user_id=user.id, 
                referred_user_id=referral.id
            ).all()
            total_earnings = sum(earning.amount for earning in earnings)
            
            referral_friends.append({
                "name": referral.full_name,
                "earnings": f"${total_earnings:,.2f}" if total_earnings > 0 else "$0.00"
            })
        
        return jsonify({
            "status": "success",
            "referral_friends": referral_friends
        })
        
    except Exception as e:
        logger.error(f"Error getting referral friends: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@referrals_bp.route("/get_daily_referral_earnings", methods=["GET"])
@login_required
def get_daily_referral_earnings():
    try:
        user = User.query.filter_by(id=current_user.id).first()
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404

        end_date = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999) # esto es para que tambien cuente el dia de hoy
        start_date = (end_date - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        earnings = ReferralEarnings.query.filter(
            ReferralEarnings.user_id == user.id,
            ReferralEarnings.created_at >= start_date,
            ReferralEarnings.created_at <= end_date
        ).order_by(ReferralEarnings.created_at.asc()).all()
        
        daily_earnings = {}
        labels = []
        
        for i in range(30):
            date = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
            labels.append(date)
            daily_earnings[date] = 0.0
        
        for earning in earnings:
            date_key = earning.created_at.strftime('%Y-%m-%d')
            if date_key in daily_earnings:
                daily_earnings[date_key] += earning.amount
        
        earnings_data = [daily_earnings[date] for date in labels]
        
        return jsonify({
            "status": "success",
            "labels": labels,
            "earnings_data": earnings_data
        })
        
    except Exception as e:
        logger.error(f"Error getting daily referral earnings: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500 