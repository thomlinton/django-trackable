"""
This module implements counters as simple wrappers around the current
``MessageBackend``.

"""
from trackable.message import connection


def send_increment_message(request, obj, field_name, data_cls=None, options={}):
    """
    Send a message for incrementing the ``field_name`` count
    for the trackable data model ``data_cls`` by ``value``.
    
    """
    if not options.get('value',None):
        options.update([('value',1)])
    connection.send_message(request, obj, field_name, 'incr', data_cls=data_cls, options=options)

def send_decrement_message(request, obj, field_name, data_cls=None, options={}):
    """
    Send a message for decrementing the ``field_name`` count
    for the trackable data model ``data_cls`` by ``value``.
    
    """
    if not options.get('value',None):
        options.update([('value',1)])
    connection.send_message(request, obj, field_name, 'decr', data_cls=data_cls, options=options)
