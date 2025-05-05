import uuid
from .create_db import db

from .users import User

class ReferralLink(db.Model):
  """Represents a referral link in the database."""
  __tablename__ = "referral_links"

  id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
  user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
  code = db.Column(db.String(255), nullable=False, unique=True)
  active = db.Column(db.Boolean, default=True)
  created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
  used_at = db.Column(db.DateTime, nullable=True)
  referred_by = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)

  user = db.relationship('User', backref=db.backref('referral_links', lazy=True), foreign_keys=[user_id])
  referrer = db.relationship('User', backref=db.backref('referred_links', lazy=True), foreign_keys=[referred_by])

  def __repr__(self):
      return f"<ReferralLink(id={self.id}, user_id={self.user_id}, code={self.code})>"
