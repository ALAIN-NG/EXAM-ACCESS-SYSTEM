from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
import logging

logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    """Gestionnaire d'exceptions personnalisé pour l'API"""
    
    # Appeler le gestionnaire d'exceptions par défaut
    response = exception_handler(exc, context)
    
    if response is None:
        # Si l'exception n'est pas gérée par DRF
        if isinstance(exc, DjangoValidationError):
            # Gérer les ValidationError de Django
            response = Response(
                {
                    'error': 'Validation Error',
                    'details': exc.message_dict if hasattr(exc, 'message_dict') else str(exc)
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        elif isinstance(exc, IntegrityError):
            # Gérer les erreurs d'intégrité de la base de données
            logger.error(f"IntegrityError: {str(exc)}")
            response = Response(
                {
                    'error': 'Database Integrity Error',
                    'details': 'Une violation de contrainte de base de données est survenue'
                },
                status=status.HTTP_409_CONFLICT
            )
        else:
            # Logger les autres exceptions non gérées
            logger.exception(f"Unhandled exception: {str(exc)}")
            response = Response(
                {
                    'error': 'Internal Server Error',
                    'details': 'Une erreur interne est survenue'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    # Ajouter des informations supplémentaires à la réponse
    if response is not None:
        # Ajouter un code d'erreur personnalisé si nécessaire
        if isinstance(response.data, dict):
            response.data['success'] = False
        
        # Logger les erreurs 4xx et 5xx
        if response.status_code >= 400:
            logger.warning(
                f"API Error - Status: {response.status_code} - "
                f"Path: {context['request'].path} - "
                f"User: {context['request'].user} - "
                f"Data: {response.data}"
            )
    
    return response


class ExamAccessException(Exception):
    """Classe de base pour les exceptions du système d'accès aux examens"""
    
    def __init__(self, message, code=None, details=None):
        self.message = message
        self.code = code
        self.details = details
        super().__init__(self.message)


class QRCodeValidationError(ExamAccessException):
    """Exception pour les erreurs de validation de QR code"""
    pass


class StudentNotAuthorizedError(ExamAccessException):
    """Exception pour les étudiants non autorisés"""
    pass


class ExamTimeError(ExamAccessException):
    """Exception pour les problèmes d'horaire d'examen"""
    pass


class PaymentRequiredError(ExamAccessException):
    """Exception pour les paiements non réglés"""
    pass


class ScanLimitExceededError(ExamAccessException):
    """Exception pour les limites de scan dépassées"""
    pass