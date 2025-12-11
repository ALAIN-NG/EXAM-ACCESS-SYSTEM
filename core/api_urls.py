# core/api_urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from . import views

router = DefaultRouter()
router.register(r'annees-academiques', views.AnneeAcademiqueViewSet)
router.register(r'filieres', views.FiliereViewSet)
router.register(r'niveaux', views.NiveauViewSet)
router.register(r'ues', views.UEViewSet)
router.register(r'salles', views.SalleViewSet)
router.register(r'sessions-examen', views.SessionExamenViewSet)
router.register(r'etudiants', views.EtudiantViewSet)
router.register(r'examens', views.ExamenViewSet, basename='examen')  # Ajoutez basename
router.register(r'controles-acces', views.ControleAccesViewSet, basename='controleacces')
router.register(r'paiements', views.PaiementViewSet)
router.register(r'inscriptions-ue', views.InscriptionUEViewSet)
router.register(r'justificatifs-absence', views.JustificatifAbsenceViewSet)
router.register(r'audit-logs', views.AuditLogViewSet)

# URL patterns spécifiques pour l'API
api_urlpatterns = [
    # API REST
    path('', include(router.urls)),
    
    # Authentification
    path('auth/token/', obtain_auth_token, name='api_token_auth'),
    path('auth/me/', views.CurrentUserView.as_view(), name='current_user'),
    path('auth/change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    
    # Tableau de bord et statistiques
    # path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('statistiques/', views.StatistiquesView.as_view(), name='statistiques'),
    
    # Scan rapide (interface surveillant)
    path('scan-rapide/', views.ScanRapideView.as_view(), name='scan_rapide'),
    
    # Vérification publique QR code
    path('verify-qr/', views.VerifyQRCodeView.as_view(), name='verify_qr'),
    
    # Interface d'administration API
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]

# Pour l'include dans le urls.py principal
urlpatterns = api_urlpatterns