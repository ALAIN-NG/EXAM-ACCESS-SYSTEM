import time
import json
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
import logging
from django.shortcuts import redirect
from .models import AuditLog
from django.contrib.auth import logout
from django.utils.crypto import get_random_string
from django.contrib import messages


logger = logging.getLogger('audit')

class AuditMiddleware(MiddlewareMixin):
    """Middleware pour l'audit des requêtes"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Enregistrer le temps de début
        start_time = time.time()
        
        # Traiter la requête
        response = self.get_response(request)
        
        # Enregistrer le temps de fin
        end_time = time.time()
        duration = end_time - start_time
        
        # Enregistrer l'audit pour certaines requêtes
        if self.should_log_request(request, response):
            self.log_request(request, response, duration)
        
        return response
    
    def should_log_request(self, request, response):
        """Déterminer si la requête doit être journalisée"""
        # Ne pas logger les requêtes statiques
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return False
        
        # Ne pas logger les requêtes d'administration (sauf si nécessaire)
        if request.path.startswith('/admin/'):
            return True  # On loggue l'admin pour la sécurité
        
        # Logger les requêtes API importantes
        if request.path.startswith('/api/'):
            # Logger les scans, paiements, etc.
            important_paths = ['/api/scan', '/api/paiements', '/api/examens', '/api/controles-acces']
            return any(request.path.startswith(path) for path in important_paths)
        
        return False
    
    def log_request(self, request, response, duration):
        """Journaliser la requête"""
        from core.models import AuditLog
        
        try:
            # Récupérer l'utilisateur
            user = request.user if not isinstance(request.user, AnonymousUser) else None
            
            # Déterminer le type d'action
            action_type = self.get_action_type(request.path, request.method)
            
            # Préparer les détails
            details = {
                'method': request.method,
                'path': request.path,
                'query_params': dict(request.GET),
                'duration': round(duration, 3),
                'status_code': response.status_code,
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            }
            
            # Ajouter les données de la requête pour certaines actions
            if action_type in ['scan', 'paiement', 'examen']:
                try:
                    # Pour les requêtes POST avec JSON
                    if request.method in ['POST', 'PUT', 'PATCH'] and request.body:
                        body = json.loads(request.body.decode('utf-8', errors='ignore'))
                        # Ne pas logger les mots de passe ou données sensibles
                        sanitized_body = self.sanitize_body(body)
                        details['request_body'] = sanitized_body
                except:
                    pass
            
            # Créer l'entrée d'audit
            AuditLog.objects.create(
                utilisateur=user,
                action_type=action_type,
                action=f"{request.method} {request.path}",
                details=details,
                ip=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )
            
            # Journaliser également dans le fichier log
            logger.info(
                f"Audit - User: {user.username if user else 'Anonymous'} - "
                f"IP: {self.get_client_ip(request)} - "
                f"Action: {request.method} {request.path} - "
                f"Status: {response.status_code} - "
                f"Duration: {duration:.3f}s"
            )
            
        except Exception as e:
            # Logger l'erreur mais ne pas interrompre le flux
            logger.error(f"Erreur dans AuditMiddleware: {str(e)}")
    
    def get_action_type(self, path, method):
        """Déterminer le type d'action basé sur le chemin"""
        path_lower = path.lower()
        
        if '/api/scan' in path_lower or '/controles-acces' in path_lower:
            return 'scan'
        elif '/api/paiements' in path_lower:
            return 'paiement'
        elif '/api/examens' in path_lower:
            return 'examen'
        elif '/api/inscriptions' in path_lower:
            return 'inscription'
        elif '/api/justificatifs' in path_lower:
            return 'justificatif'
        elif '/admin/' in path_lower:
            return 'admin'
        elif '/api/auth/' in path_lower:
            return 'authentication'
        else:
            return 'api'
    
    def get_client_ip(self, request):
        """Récupérer l'adresse IP du client"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def sanitize_body(self, body):
        """Sanitizer le corps de la requête pour enlever les données sensibles"""
        if isinstance(body, dict):
            sanitized = body.copy()
            # Masquer les mots de passe et tokens
            sensitive_fields = ['password', 'token', 'secret', 'key', 'authorization']
            for field in sensitive_fields:
                if field in sanitized:
                    sanitized[field] = '***MASKED***'
            return sanitized
        return body


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Middleware pour ajouter des en-têtes de sécurité"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Ajouter les en-têtes de sécurité
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        
        # CSP (Content Security Policy) - ajustez selon vos besoins
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "form-action 'self'; "
            "base-uri 'self';"
        )
        response['Content-Security-Policy'] = csp
        
        # HSTS (HTTPS Strict Transport Security)
        if not request.META.get('HTTP_HOST', '').startswith('localhost'):
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        return response
    





class SessionManagementMiddleware:
    """Middleware pour gérer les sessions utilisateur"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Vérifier si l'utilisateur est authentifié
        if request.user.is_authenticated:
            # Vérifier la validité de la session
            session_key = request.session.session_key
            
            # Mettre à jour le timestamp de dernière activité
            request.session['last_activity'] = str(timezone.now())
            
            # Vérifier si la session est expirée (optionnel)
            if 'last_activity' in request.session:
                last_activity_str = request.session['last_activity']
                try:
                    last_activity = timezone.datetime.fromisoformat(last_activity_str)
                    timeout_duration = timezone.timedelta(minutes=30)
                    
                    if timezone.now() - last_activity > timeout_duration:
                        # Session expirée - déconnecter l'utilisateur
                        user = request.user
                        logout(request)
                        
                        # Log l'action
                        AuditLog.objects.create(
                            utilisateur=user,
                            action_type='system',
                            action='Session expirée - Déconnexion automatique',
                            details={'session_key': session_key},
                            ip=request.META.get('REMOTE_ADDR')
                        )
                        
                        messages.info(request, "Votre session a expiré. Veuillez vous reconnecter.")
                        return redirect('login')
                except:
                    pass
        
        response = self.get_response(request)
        return response
    





class MultiTabSessionMiddleware:
    """
    Middleware pour gérer plusieurs sessions simultanées dans différents onglets
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Vérifier le cookie d'onglet
        tab_id = request.COOKIES.get('tab_id')
        
        if tab_id:
            request.tab_id = tab_id
            
            # Si l'utilisateur est authentifié, vérifier la cohérence
            if request.user.is_authenticated:
                session_tab_id = request.session.get('tab_id')
                
                # Si le tab_id de la session ne correspond pas au cookie
                if session_tab_id and session_tab_id != tab_id:
                    # Mettre à jour le tab_id dans la session
                    request.session['tab_id'] = tab_id
        
        # Traiter la requête
        response = self.get_response(request)
        
        # Mettre à jour le timestamp d'activité
        if request.user.is_authenticated and hasattr(request, 'tab_id'):
            # Initialiser last_activity comme dictionnaire si ce n'est pas déjà le cas
            if 'last_activity' not in request.session:
                request.session['last_activity'] = {}
            elif isinstance(request.session['last_activity'], str):
                # Si last_activity est une chaîne, la convertir en dictionnaire
                try:
                    request.session['last_activity'] = json.loads(request.session['last_activity'])
                except (json.JSONDecodeError, TypeError):
                    request.session['last_activity'] = {}
            
            # Mettre à jour le timestamp pour cet onglet
            tab_id = getattr(request, 'tab_id', None)
            if tab_id:
                request.session['last_activity'][tab_id] = timezone.now().isoformat()
                request.session.modified = True
        
        return response
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        """Vérifier les sessions avant d'exécuter la vue"""
        # Ignorer pour les vues de login
        if view_func.__name__ in ['universal_login_view', 'student_login_view']:
            return None
        
        # Ignorer pour la vue logout
        if request.path.startswith('/logout'):
            return None
        
        # Vérifier l'expiration de session pour cet onglet
        if request.user.is_authenticated and hasattr(request, 'tab_id'):
            tab_id = request.tab_id
            
            # Récupérer last_activity en s'assurant que c'est un dictionnaire
            last_activity_data = request.session.get('last_activity')
            if isinstance(last_activity_data, str):
                try:
                    last_activity_data = json.loads(last_activity_data)
                except (json.JSONDecodeError, TypeError):
                    last_activity_data = {}
            
            if last_activity_data and isinstance(last_activity_data, dict):
                last_activity_str = last_activity_data.get(tab_id)
                
                if last_activity_str:
                    try:
                        last_active = timezone.datetime.fromisoformat(last_activity_str)
                        timeout = timezone.timedelta(hours=2)  # 2 heures d'inactivité
                        
                        if timezone.now() - last_active > timeout:
                            # Session expirée pour cet onglet
                            logout(request)
                            from django.contrib import messages
                            messages.info(request, "Votre session a expiré en raison d'une inactivité prolongée.")
                            from django.shortcuts import redirect
                            return redirect('login')
                    except (ValueError, TypeError):
                        # En cas d'erreur de parsing, on ignore
                        pass
        
        return None



class TabSpecificSessionMiddleware:
    """
    Crée des sessions spécifiques à chaque onglet en ajoutant un suffixe
    basé sur l'ID d'onglet au cookie de session
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Lire l'ID d'onglet depuis le cookie ou l'en-tête
        tab_id = self.get_tab_id(request)
        
        if tab_id:
            # Modifier le nom du cookie de session pour cet onglet
            original_session_key = request.session.session_key
            
            # Si c'est une nouvelle session ou un nouvel onglet
            if not original_session_key or not request.session.get('tab_bound'):
                # Générer une nouvelle clé de session pour cet onglet
                request.session.cycle_key()
                request.session['tab_bound'] = True
                request.session['tab_id'] = tab_id
                request.session['created_at'] = timezone.now().isoformat()
        
        response = self.get_response(request)
        
        # Nettoyer les anciennes sessions
        self.cleanup_old_tabs(request)
        
        return response
    
    def get_tab_id(self, request):
        """Obtenir ou générer un ID d'onglet"""
        tab_id = request.COOKIES.get('tab_id')
        
        if not tab_id:
            # Générer un ID basé sur le timestamp et un random
            import uuid
            tab_id = f"tab_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            request.new_tab = True
        else:
            request.new_tab = False
        
        return tab_id
    
    def cleanup_old_tabs(self, request):
        """Nettoyer les données de session des onglets inactifs"""
        if 'tab_sessions' in request.session:
            # Garder seulement les sessions actives des dernières 24h
            twenty_four_hours_ago = timezone.now() - timezone.timedelta(hours=24)
            
            active_tabs = {}
            for tab_id, tab_data in request.session['tab_sessions'].items():
                last_activity = timezone.datetime.fromisoformat(tab_data['last_activity'])
                if last_activity > twenty_four_hours_ago:
                    active_tabs[tab_id] = tab_data
            
            request.session['tab_sessions'] = active_tabs


