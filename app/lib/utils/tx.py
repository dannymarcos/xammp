from flask import current_app
import time
import json
from collections import defaultdict
from threading import Lock

subscriptions = defaultdict(list)
subscription_lock = Lock()

def subscribe(email):
    """Crea una cola de mensajes para un usuario"""
    queue = []
    with subscription_lock:
        subscriptions[email].append(queue)
    return queue

def unsubscribe(email, queue):
    """Elimina la cola de mensajes del usuario"""
    with subscription_lock:
        if email in subscriptions and queue in subscriptions[email]:
            subscriptions[email].remove(queue)

def emit(email, event, data):
    """Envía un evento a un usuario específico con formato SSE correcto"""
    # Formato completo con event y data
    message = f"event: {event}\ndata: {json.dumps(data)}\n\n"
    
    with subscription_lock:
        if email in subscriptions:
            for queue in subscriptions[email][:]:
                try:
                    queue.append(message)
                    current_app.logger.debug(f"📤 Evento '{event}' enviado a {email}")
                except Exception as e:
                    # unsubscribe(email, queue)
                    pass