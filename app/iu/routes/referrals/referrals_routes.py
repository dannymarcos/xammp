from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from app.models.referral_link import ReferralLink
from app.models.users import User
from app.Aplicacion import db
import logging

referrals_bp = Blueprint('referrals', __name__)
logger = logging.getLogger(__name__)

@referrals_bp.route("/referrals", methods=['GET', 'POST'])
@login_required
def referrals():
    if request.method == 'GET':
        return render_template("referrals.html", is_admin=(current_user.role == "admin"))
    return render_template("under_construction.html")

@referrals_bp.route("/generate_referral_link", methods=["GET"])
@login_required
def generate_referral_link():
    try:
        user = User.query.filter_by(id=current_user.id).first()
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404
        existing_link = ReferralLink.query.filter_by(user_id=user.id, active=True).first()
        if existing_link:
            referral_code = existing_link.code
        else:
            total_referrals = ReferralLink.query.filter_by(active=False).count()
            referral_number = str(total_referrals + 1).zfill(2)
            referral_code = f"linkreferidosaegiaiaapp{referral_number}"
            new_link = ReferralLink(user_id=user.id, code=referral_code, active=True)
            db.session.add(new_link)
            db.session.commit()
        direct_referrals = []
        direct_refs = ReferralLink.query.filter_by(referred_by=user.id, active=False).all()
        for ref in direct_refs:
            ref_user = User.query.get(ref.user_id)
            if ref_user:
                direct_referrals.append({
                    "name": ref_user.full_name,
                    "date": ref.used_at.strftime("%Y-%m-%d") if ref.used_at else "N/A"
                })
        indirect_referrals = []
        for direct_ref in direct_refs:
            indirect_refs = ReferralLink.query.filter_by(referred_by=direct_ref.user_id, active=False).all()
            for ref in indirect_refs:
                ref_user = User.query.get(ref.user_id)
                referrer = User.query.get(direct_ref.user_id)
                if ref_user and referrer:
                    indirect_referrals.append({
                        "name": ref_user.full_name,
                        "date": ref.used_at.strftime("%Y-%m-%d") if ref.used_at else "N/A",
                        "referred_by": referrer.full_name
                    })
        total_referrals = len(direct_referrals) + len(indirect_referrals)
        return jsonify({
            "status": "success",
            "referral_link": referral_code,
            "direct_referrals": direct_referrals,
            "indirect_referrals": indirect_referrals,
            "total_referrals": total_referrals
        })
    except Exception as e:
        logger.error(f"Error generating referral link: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500 