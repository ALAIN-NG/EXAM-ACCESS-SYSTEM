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
            html_email_template_name='registration/password_reset_email.html',
            subject_template_name='registration/password_reset_subject.txt',
            success_url='done/',
            extra_email_context={
                'site_name': 'SG Examens',
                'protocol': 'https',
                'domain': 'localhost:8000',
            }
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
    path('examens/', views.examen_list1, name='examen_list'),
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
    path('operations/', views.Operations, name='operations'),
    
    # Années académiques
    path('annee/', views.annee_list, name='annee_list'),
    path('annee/nouveau/', views.annee_create, name='annee_create'),
    path('annee/<int:pk>/modifier/', views.annee_update, name='annee_update'),
    path('annee/<int:pk>/supprimer/', views.annee_delete, name='annee_delete'),
    
    # Filieres
    path('filiere/', views.filiere_list, name='filiere_list'),
    path('filiere/nouveau/', views.filiere_create, name='filiere_create'),
    path('filiere/<int:pk>/modifier/', views.filiere_update, name='filiere_update'),
    path('filiere/<int:pk>/supprimer/', views.filiere_delete, name='filiere_delete'),
    
    # Niveaux
    path('niveau/', views.niveau_list, name='niveau_list'),
    path('niveau/nouveau/', views.niveau_create, name='niveau_create'),
    path('niveau/<int:pk>/modifier/', views.niveau_update, name='niveau_update'),
    path('niveau/<int:pk>/supprimer/', views.niveau_delete, name='niveau_delete'),
    
    # UEs
    path('ue/', views.ue_list, name='ue_list'),
    path('ue/nouveau/', views.ue_create, name='ue_create'),
    path('ue/<int:pk>/modifier/', views.ue_update, name='ue_update'),
    path('ue/<int:pk>/supprimer/', views.ue_delete, name='ue_delete'),
    
    # Étudiants
    path('etudiant/', views.etudiant_list, name='etudiant_list'),
    path('etudiant/nouveau/', views.etudiant_create, name='etudiant_create'),
    path('etudiant/<int:pk>/', views.etudiant_detail, name='etudiant_detail'),
    path('etudiant/<int:pk>/modifier/', views.etudiant_update, name='etudiant_update'),
    path('etudiant/<int:pk>/supprimer/', views.etudiant_delete, name='etudiant_delete'),
    
    # Paiements
    path('paiement/', views.paiement_list, name='paiement_list'),
    path('paiement/nouveau/', views.paiement_create, name='paiement_create'),
    path('paiement/<int:pk>/modifier/', views.paiement_update, name='paiement_update'),
    path('paiement/<int:pk>/supprimer/', views.paiement_delete, name='paiement_delete'),
    
    # Inscriptions UE
    path('inscription/', views.inscription_list, name='inscription_list'),
    path('inscription/nouveau/', views.inscription_create, name='inscription_create'),
    path('inscription/<int:pk>/modifier/', views.inscription_update, name='inscription_update'),
    path('inscription/<int:pk>/supprimer/', views.inscription_delete, name='inscription_delete'),
    
    # Salles
    path('salle/', views.salle_list, name='salle_list'),
    path('salle/nouveau/', views.salle_create, name='salle_create'),
    path('salle/<int:pk>/modifier/', views.salle_update, name='salle_update'),
    path('salle/<int:pk>/supprimer/', views.salle_delete, name='salle_delete'),
    
    # Sessions d'examen
    path('session/', views.session_list, name='session_list'),
    path('session/nouveau/', views.session_create, name='session_create'),
    path('session/<int:pk>/modifier/', views.session_update, name='session_update'),
    path('session/<int:pk>/supprimer/', views.session_delete, name='session_delete'),
    
    # Examens
    path('examen/', views.examen_list1, name='examen_list1'),
    path('examen/nouveau/', views.examen_create, name='examen_create'),
    path('examen/<int:pk>/', views.examen_detail, name='examen_detail'),
    path('examen/<int:pk>/modifier/', views.examen_update, name='examen_update'),
    path('examen/<int:pk>/supprimer/', views.examen_delete, name='examen_delete'),
]

# ============================================
# GESTION DES ERREURS
# ============================================
handler404 = 'core.views.handler404'
handler500 = 'core.views.handler500'

