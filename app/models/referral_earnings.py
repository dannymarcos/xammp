import uuid
from datetime import datetime
from .create_db import db

class ReferralEarnings(db.Model):
    __tablename__ = 'referral_earnings'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    referred_user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id], backref='referral_earnings')
    referred_user = db.relationship('User', foreign_keys=[referred_user_id])


def add_referral_earning(user_id, referred_user_id, amount):
    try:
        new_earning = ReferralEarnings(
            user_id=user_id,
            referred_user_id=referred_user_id,
            amount=amount
        )
        db.session.add(new_earning)
        db.session.commit()
        return new_earning
    except Exception as e:
        db.session.rollback()
        print(f"Error adding referral earning: {e}")
        return None


def get_user_referral_earnings(user_id):
    try:
        return ReferralEarnings.query.filter_by(user_id=user_id).order_by(ReferralEarnings.created_at.desc()).all()
    except Exception as e:
        print(f"Error getting referral earnings: {e}")
        return []


def get_total_referral_earnings(user_id):
    try:
        result = db.session.query(db.func.sum(ReferralEarnings.amount)).filter_by(user_id=user_id).scalar()
        return result or 0.0
    except Exception as e:
        print(f"Error calculating total referral earnings: {e}")
        return 0.0


def get_referral_earnings_by_period(user_id, start_date=None, end_date=None):
    try:
        query = ReferralEarnings.query.filter_by(user_id=user_id)
        
        if start_date:
            query = query.filter(ReferralEarnings.created_at >= start_date)
        if end_date:
            query = query.filter(ReferralEarnings.created_at <= end_date)
            
        return query.order_by(ReferralEarnings.created_at.desc()).all()
    except Exception as e:
        print(f"Error getting referral earnings by period: {e}")
        return [] 