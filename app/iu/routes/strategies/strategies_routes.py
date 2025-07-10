from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.models.strategies import get_all_strategies_from_user, Strategy
from app.Aplicacion import db

strategies_bp = Blueprint('strategies', __name__)

@strategies_bp.route("/strategies", methods=['GET', 'POST', 'DELETE'])
@login_required
def strategies():
    if request.method == 'GET':
        all_strategies_from_user = get_all_strategies_from_user(current_user.id)
        
        return jsonify({'strategies': all_strategies_from_user})
   
    data = request.get_json()
    if request.method == 'POST':
        text = data.get('text')
        name = data.get('name')
        strategy = Strategy(user_id=current_user.id, text=text, name=name)
        db.session.add(strategy)
        db.session.commit()
        return jsonify({'message': 'Strategy saved successfully'})
    
    if request.method == "DELETE":
        strategy_id = data.get('id')
        strategy = Strategy.query.filter_by(user_id=current_user.id, id=strategy_id).first()
        if strategy:
            db.session.delete(strategy)
            db.session.commit()
            return jsonify({'message': 'Strategy deleted successfully'})
        else:
            return jsonify({'message': 'Strategy not found'}), 404
        
    return jsonify({'message': 'Invalid request method'}), 400
