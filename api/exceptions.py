"""
Custom exception handler for REST framework
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    
    if response is not None:
        response.data['status_code'] = response.status_code
        return response
    
    # 处理未预期的异常
    return Response({
        'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR,
        'message': str(exc) if str(exc) else 'Internal server error',
        'data': None
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
