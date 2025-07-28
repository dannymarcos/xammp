import time
from flask import Blueprint, render_template, session, redirect, url_for
from flask_login import login_required, current_user
import logging

from app.lib.utils.tx import subscribe, unsubscribe


see_bp = Blueprint('see', __name__)
logger = logging.getLogger(__name__)

@see_bp.route("/sse/<email>")
@login_required
def sse(email):
    from flask import Response, stream_with_context
    
    # Verificar que el usuario esté autenticado
    if not current_user.is_authenticated or current_user.email != email:
        return "Unauthorized", 403
    
    queue = subscribe(email)
    
    def event_stream():
        try:
            while True:
                if queue:
                    yield f"data: {queue.pop(0)}\n\n"
                time.sleep(0.5)  # Reduce la carga del CPU
        except GeneratorExit:
            unsubscribe(email, queue)
    
    response = Response(
        stream_with_context(event_stream()),
        mimetype='text/event-stream'
    )
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response
