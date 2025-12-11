# core/urls.py
from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # ============================================
    # PAGES PUBLIQUES (sans authentification)
    # ============================================
    path('', views.home_view, name='home'),
    
    # ============================================
    # AUTHENTIFICATION
    # ============================================
    
    # Login universel (pour tous les utilisateurs)
    path('login/', views.universal_login_view, name='login'),
    
    # Logout (nécessite POST)
    path('logout/', auth_views.LogoutView.as_view(
        template_name='registration/logged_out.html',
        next_page='home'
    ), name='logout'),
    
    # Réinitialisation de mot de passe
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset_form.html',
             email_template_name='registration/password_reset_email.html',
             subject_template_name='registration/password_reset_subject.txt',
             success_url='done/'
         ), 
         name='password_reset'),
    
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html'
         ), 
         name='password_reset_done'),
    
    path('password-reset-confirm/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html',
             success_url='/password-reset-complete/'
         ), 
         name='password_reset_confirm'),
    
    path('password-reset-complete/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html'
         ), 
         name='password_reset_complete'),
    
    # Changement de mot de passe (utilisateur connecté)
    path('password-change/', 
         auth_views.PasswordChangeView.as_view(
             template_name='registration/password_change_form.html',
             success_url='done/'
         ), 
         name='password_change'),
    
    path('password-change/done/', 
         auth_views.PasswordChangeDoneView.as_view(
             template_name='registration/password_change_done.html'
         ), 
         name='password_change_done'),
    
    # ============================================
    # TABLEAUX DE BORD (selon le type d'utilisateur)
    # ============================================
    
    # Tableau de bord principal (personnel/surveillants/enseignants)
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # Espace étudiant
    path('student/', views.student_dashboard, name='student_dashboard'),
    path('student/examens/', views.student_examens, name='student_examens'),
    
    # ============================================
    # GESTION DES EXAMENS
    # ============================================
    
    # Liste et détails des examens
    path('examens/', views.examen_list, name='examen_list'),
    path('examens/<int:pk>/', views.examen_detail, name='examen_detail'),
    path('examens/<int:pk>/rapport/', views.examen_rapport, name='examen_rapport'),
    
    # ============================================
    # SCANNER QR CODE
    # ============================================
    
    # Interface de scan (pour surveillants)
    path('scan/', views.scan_interface, name='scan_interface'),
    path('scan/<int:examen_id>/', views.scan_examen, name='scan_examen'),
    
    # ============================================
    # FONCTIONNALITÉS ÉTUDIANTS
    # ============================================
    
    # QR Code étudiant
    path('student/qr/', views.student_qr, name='student_qr'),
    path('student/qr/download/', views.download_qr, name='download_qr'),
    path('student/qr/generate/', views.generate_qr_code_api, name='generate_qr_code_api'),
    
    # Justificatifs d'absence
    path('student/justificatifs/ajouter/', 
         views.add_justificatif, 
         name='add_justificatif'),
    
    path('student/justificatifs/ajouter/<int:examen_id>/', 
         views.add_justificatif, 
         name='add_justificatif_examen'),
    
    # ============================================
    # PROFIL ET PARAMÈTRES
    # ============================================
    
    # Profil utilisateur
    path('profile/', views.profile_view, name='profile'),
    
    # Documentation
    path('docs/', views.documentation_view, name='documentation'),
    
    # ============================================
    # API REST
    # ============================================
    
    path('api/', include('core.api_urls')),
    
    # ============================================
    # URLS DE DÉVELOPPEMENT/DÉBOGAGE
    # ============================================
    
    # Désactivez ces URLs en production
    # path('debug/urls/', views.debug_urls, name='debug_urls'),
]

# ============================================
# GESTION DES ERREURS
# ============================================
handler404 = 'core.views.handler404'
handler500 = 'core.views.handler500'