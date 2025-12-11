from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Q
import csv
from django.http import HttpResponse
from rangefilter.filters import DateRangeFilter, DateTimeRangeFilter

# Import des modèles
from .models import (
    AnneeAcademique, Filiere, Niveau, UE, Etudiant,
    Paiement, InscriptionUE, Salle, SessionExamen,
    Examen, ControleAcces, JustificatifAbsence, AuditLog
)

# ========================================================
# ACTIONS ADMINISTRATIVES COMMUNES
# ========================================================

def exporter_csv(modeladmin, request, queryset):
    """Action pour exporter les données en CSV"""
    meta = modeladmin.model._meta
    field_names = [field.name for field in meta.fields]
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename={meta.verbose_name_plural}.csv'
    
    writer = csv.writer(response)
    writer.writerow(field_names)
    
    for obj in queryset:
        row = [getattr(obj, field) for field in field_names]
        writer.writerow(row)
    
    return response

exporter_csv.short_description = "Exporter en CSV"


def activer_selection(modeladmin, request, queryset):
    """Activer les éléments sélectionnés"""
    queryset.update(active=True)
    modeladmin.message_user(request, f"{queryset.count()} éléments activés.")

activer_selection.short_description = "Activer la sélection"


def desactiver_selection(modeladmin, request, queryset):
    """Désactiver les éléments sélectionnés"""
    queryset.update(active=False)
    modeladmin.message_user(request, f"{queryset.count()} éléments désactivés.")

desactiver_selection.short_description = "Désactiver la sélection"


def marquer_comme_regle(modeladmin, request, queryset):
    """Marquer les paiements comme réglés"""
    updated = queryset.update(est_regle=True, date_paiement=timezone.now())
    modeladmin.message_user(request, f"{updated} paiements marqués comme réglés.")

marquer_comme_regle.short_description = "Marquer comme réglé"


def autoriser_examen(modeladmin, request, queryset):
    """Autoriser les étudiants à passer l'examen"""
    updated = queryset.update(est_autorise_examen=True)
    modeladmin.message_user(request, f"{updated} étudiants autorisés pour l'examen.")

autoriser_examen.short_description = "Autoriser pour examen"


# ========================================================
# FILTRES PERSONNALISÉS
# ========================================================

class StatutEtudiantFilter(admin.SimpleListFilter):
    """Filtre par statut étudiant"""
    title = 'Statut'
    parameter_name = 'statut'
    
    def lookups(self, request, model_admin):
        return [
            ('actif', 'Actifs'),
            ('suspendu', 'Suspendus'),
            ('exclu', 'Exclus'),
            ('diplome', 'Diplômés'),
        ]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(statut=self.value())
        return queryset


class PaiementRegleFilter(admin.SimpleListFilter):
    """Filtre par statut de paiement"""
    title = 'Paiement réglé'
    parameter_name = 'est_regle'
    
    def lookups(self, request, model_admin):
        return [
            ('oui', 'Réglés'),
            ('non', 'Non réglés'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'oui':
            return queryset.filter(est_regle=True)
        elif self.value() == 'non':
            return queryset.filter(est_regle=False)
        return queryset


class AutorisationExamenFilter(admin.SimpleListFilter):
    """Filtre par autorisation examen"""
    title = 'Autorisé examen'
    parameter_name = 'est_autorise'
    
    def lookups(self, request, model_admin):
        return [
            ('oui', 'Autorisés'),
            ('non', 'Non autorisés'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'oui':
            return queryset.filter(est_autorise_examen=True)
        elif self.value() == 'non':
            return queryset.filter(est_autorise_examen=False)
        return queryset


# ========================================================
# INLINES (pour les relations)
# ========================================================

class PaiementInline(admin.TabularInline):
    """Inline pour les paiements dans l'admin étudiant"""
    model = Paiement
    extra = 0
    fields = ('annee_academique', 'montant_attendu', 'montant', 'est_regle', 'date_paiement')
    readonly_fields = ('date_paiement',)
    can_delete = False


class InscriptionUEInline(admin.TabularInline):
    """Inline pour les inscriptions UE dans l'admin étudiant"""
    model = InscriptionUE
    extra = 0
    fields = ('ue', 'annee_academique', 'est_autorise_examen', 'date_inscription')
    readonly_fields = ('date_inscription',)
    can_delete = False
    show_change_link = True


class ControleAccesInline(admin.TabularInline):
    """Inline pour les contrôles d'accès dans l'admin examen"""
    model = ControleAcces
    extra = 0
    fields = ('etudiant', 'scan_method', 'autorise', 'raison_refus', 'date_scan')
    readonly_fields = ('date_scan', 'raison_refus')
    can_delete = False
    max_num = 0  # Lecture seule
    
    def has_add_permission(self, request, obj=None):
        return False


class JustificatifAbsenceInline(admin.TabularInline):
    """Inline pour les justificatifs dans l'admin examen"""
    model = JustificatifAbsence
    extra = 0
    fields = ('etudiant', 'type_justificatif', 'statut', 'date_depot', 'traite_par')
    readonly_fields = ('date_depot',)
    can_delete = False


# ========================================================
# MODELADMIN PERSONNALISÉS
# ========================================================

@admin.register(AnneeAcademique)
class AnneeAcademiqueAdmin(admin.ModelAdmin):
    """Administration des années académiques"""
    list_display = ('code', 'active', 'date_creation')
    list_filter = ('active',)
    search_fields = ('code',)
    actions = [activer_selection, desactiver_selection, exporter_csv]
    readonly_fields = ('date_creation', 'date_modification')
    
    fieldsets = (
        ('Informations', {
            'fields': ('code', 'active')
        }),
        ('Dates', {
            'fields': ('date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Filiere)
class FiliereAdmin(admin.ModelAdmin):
    """Administration des filières"""
    list_display = ('code', 'nom', 'date_creation')
    search_fields = ('code', 'nom')
    actions = [exporter_csv]
    readonly_fields = ('date_creation', 'date_modification')


@admin.register(Niveau)
class NiveauAdmin(admin.ModelAdmin):
    """Administration des niveaux"""
    list_display = ('nom', 'ordre', 'date_creation')
    list_editable = ('ordre',)
    ordering = ('ordre',)
    actions = [exporter_csv]
    readonly_fields = ('date_creation', 'date_modification')


@admin.register(UE)
class UEAdmin(admin.ModelAdmin):
    """Administration des Unités d'Enseignement"""
    list_display = ('code', 'intitule', 'filiere', 'niveau', 'semestre', 'credit')
    list_filter = ('filiere', 'niveau', 'semestre')
    search_fields = ('code', 'intitule')
    actions = [exporter_csv]
    readonly_fields = ('date_creation', 'date_modification')
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('code', 'intitule', 'credit')
        }),
        ('Structure académique', {
            'fields': ('filiere', 'niveau', 'semestre')
        }),
        ('Dates', {
            'fields': ('date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Etudiant)
class EtudiantAdmin(admin.ModelAdmin):
    """Administration des étudiants"""
    list_display = ('matricule', 'nom', 'prenom', 'filiere', 'niveau', 'statut', 'qr_token_short', 'photo_preview')
    list_filter = (StatutEtudiantFilter, 'filiere', 'niveau')
    search_fields = ('matricule', 'nom', 'prenom', 'email')
    actions = [exporter_csv, 'changer_statut_actif', 'changer_statut_suspendu']
    readonly_fields = ('qr_token', 'date_creation', 'date_modification', 'photo_preview')
    inlines = [PaiementInline, InscriptionUEInline]
    
    fieldsets = (
        ('Informations personnelles', {
            'fields': ('matricule', 'nom', 'prenom', 'date_naissance')
        }),
        ('Coordonnées', {
            'fields': ('email', 'telephone', 'photo', 'photo_preview')
        }),
        ('Informations académiques', {
            'fields': ('filiere', 'niveau', 'statut')
        }),
        ('Sécurité', {
            'fields': ('qr_token',),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )
    
    def qr_token_short(self, obj):
        """Afficher un token QR raccourci"""
        return str(obj.qr_token)[:8] + "..."
    qr_token_short.short_description = "Token QR"
    
    def photo_preview(self, obj):
        """Aperçu de la photo"""
        if obj.photo:
            return format_html('<img src="{}" width="50" height="50" style="border-radius: 5px;" />', obj.photo.url)
        return "Aucune photo"
    photo_preview.short_description = "Photo"
    
    def changer_statut_actif(self, request, queryset):
        """Changer le statut des étudiants sélectionnés en 'actif'"""
        updated = queryset.update(statut='actif')
        self.message_user(request, f"{updated} étudiants marqués comme actifs.")
    changer_statut_actif.short_description = "Marquer comme actif"
    
    def changer_statut_suspendu(self, request, queryset):
        """Changer le statut des étudiants sélectionnés en 'suspendu'"""
        updated = queryset.update(statut='suspendu')
        self.message_user(request, f"{updated} étudiants suspendus.")
    changer_statut_suspendu.short_description = "Suspendre"
    
    def get_queryset(self, request):
        """Optimiser les requêtes avec select_related"""
        return super().get_queryset(request).select_related('filiere', 'niveau')


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    """Administration des paiements"""
    list_display = ('etudiant', 'annee_academique', 'montant', 'montant_attendu', 'est_regle', 'date_paiement', 'created_by')
    list_filter = (PaiementRegleFilter, 'annee_academique', ('date_paiement', DateRangeFilter))
    search_fields = ('etudiant__matricule', 'etudiant__nom', 'etudiant__prenom')
    actions = [exporter_csv, marquer_comme_regle]
    readonly_fields = ('date_creation', 'date_modification', 'created_by')
    
    fieldsets = (
        ('Informations de paiement', {
            'fields': ('etudiant', 'annee_academique', 'montant_attendu', 'montant', 'est_regle', 'date_paiement')
        }),
        ('Traçabilité', {
            'fields': ('created_by', 'date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Enregistrer l'utilisateur qui crée/modifie"""
        if not obj.pk:  # Si création
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        """Optimiser les requêtes avec select_related"""
        return super().get_queryset(request).select_related('etudiant', 'annee_academique', 'created_by')


@admin.register(InscriptionUE)
class InscriptionUEAdmin(admin.ModelAdmin):
    """Administration des inscriptions UE"""
    list_display = ('etudiant', 'ue', 'annee_academique', 'est_autorise_examen', 'date_inscription')
    list_filter = (AutorisationExamenFilter, 'annee_academique', 'ue__filiere', 'ue__niveau')
    search_fields = ('etudiant__matricule', 'etudiant__nom', 'ue__code', 'ue__intitule')
    actions = [exporter_csv, autoriser_examen]
    readonly_fields = ('date_inscription', 'date_creation', 'date_modification', 'created_by')
    
    fieldsets = (
        ('Inscription', {
            'fields': ('etudiant', 'ue', 'annee_academique', 'est_autorise_examen')
        }),
        ('Traçabilité', {
            'fields': ('created_by', 'date_inscription', 'date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Enregistrer l'utilisateur qui crée/modifie"""
        if not obj.pk:  # Si création
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        """Optimiser les requêtes avec select_related"""
        return super().get_queryset(request).select_related('etudiant', 'ue', 'annee_academique', 'ue__filiere', 'ue__niveau')


@admin.register(Salle)
class SalleAdmin(admin.ModelAdmin):
    """Administration des salles"""
    list_display = ('code', 'batiment', 'etage', 'capacite', 'examen_count')
    list_filter = ('batiment', 'etage')
    search_fields = ('code', 'batiment')
    actions = [exporter_csv]
    readonly_fields = ('date_creation', 'date_modification')
    
    def examen_count(self, obj):
        """Compter le nombre d'examens programmés dans cette salle"""
        count = Examen.objects.filter(salle=obj).count()
        url = reverse('admin:core_examen_changelist') + f'?salle__id__exact={obj.id}'
        return format_html('<a href="{}">{}</a>', url, count)
    examen_count.short_description = "Examens programmés"


@admin.register(SessionExamen)
class SessionExamenAdmin(admin.ModelAdmin):
    """Administration des sessions d'examen"""
    list_display = ('nom', 'type_session', 'annee_academique', 'date_debut', 'date_fin', 'active', 'examen_count')
    list_filter = ('type_session', 'active', 'annee_academique')
    search_fields = ('nom',)
    actions = [activer_selection, desactiver_selection, exporter_csv]
    readonly_fields = ('date_creation', 'date_modification', 'created_by')
    
    fieldsets = (
        ('Informations de session', {
            'fields': ('nom', 'type_session', 'annee_academique', 'date_debut', 'date_fin', 'active')
        }),
        ('Traçabilité', {
            'fields': ('created_by', 'date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )
    
    def examen_count(self, obj):
        """Compter le nombre d'examens dans la session"""
        count = Examen.objects.filter(session=obj).count()
        url = reverse('admin:core_examen_changelist') + f'?session__id__exact={obj.id}'
        return format_html('<a href="{}">{}</a>', url, count)
    examen_count.short_description = "Nombre d'examens"
    
    def save_model(self, request, obj, form, change):
        """Enregistrer l'utilisateur qui crée/modifie"""
        if not obj.pk:  # Si création
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Examen)
class ExamenAdmin(admin.ModelAdmin):
    """Administration des examens"""
    list_display = ('ue', 'date', 'heure_debut', 'heure_fin', 'salle', 'surveillant', 'type_examen', 'session', 'duree_display', 'present_count')
    list_filter = ('type_examen', 'session', 'ue__filiere', 'ue__niveau', ('date', DateRangeFilter))
    search_fields = ('ue__code', 'ue__intitule', 'salle__code')
    actions = [exporter_csv, 'generer_liste_presence']
    readonly_fields = ('date_creation', 'date_modification', 'created_by', 'duree')
    inlines = [ControleAccesInline, JustificatifAbsenceInline]
    
    fieldsets = (
        ('Informations de l\'examen', {
            'fields': ('ue', 'annee_academique', 'session', 'type_examen')
        }),
        ('Programmation', {
            'fields': ('date', 'heure_debut', 'heure_fin', 'duree')
        }),
        ('Organisation', {
            'fields': ('salle', 'surveillant')
        }),
        ('Traçabilité', {
            'fields': ('created_by', 'date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )
    
    def duree_display(self, obj):
        """Afficher la durée de manière lisible"""
        return f"{obj.duree} min"
    duree_display.short_description = "Durée"
    
    def present_count(self, obj):
        """Afficher le nombre d'étudiants présents"""
        total = InscriptionUE.objects.filter(
            ue=obj.ue,
            annee_academique=obj.annee_academique,
            est_autorise_examen=True
        ).count()
        
        presents = ControleAcces.objects.filter(
            examen=obj,
            autorise=True
        ).count()
        
        url = reverse('admin:core_controleacces_changelist') + f'?examen__id__exact={obj.id}'
        return format_html('<a href="{}">{} / {}</a>', url, presents, total)
    present_count.short_description = "Présents / Inscrits"
    
    def generer_liste_presence(self, request, queryset):
        """Générer une liste de présence pour les examens sélectionnés"""
        if len(queryset) != 1:
            self.message_user(request, "Veuillez sélectionner un seul examen.", level='error')
            return
        
        examen = queryset.first()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="liste_presence_{examen.ue.code}_{examen.date}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Liste de présence', f'Examen: {examen.ue.code}', f'Date: {examen.date}'])
        writer.writerow(['Matricule', 'Nom', 'Prénom', 'Présent', 'Heure scan', 'Méthode'])
        
        controles = ControleAcces.objects.filter(examen=examen).select_related('etudiant')
        for controle in controles:
            writer.writerow([
                controle.etudiant.matricule,
                controle.etudiant.nom,
                controle.etudiant.prenom,
                'OUI' if controle.autorise else 'NON',
                controle.date_scan.strftime('%H:%M:%S') if controle.date_scan else '',
                controle.get_scan_method_display()
            ])
        
        return response
    generer_liste_presence.short_description = "Générer liste de présence"
    
    def save_model(self, request, obj, form, change):
        """Enregistrer l'utilisateur qui crée/modifie"""
        if not obj.pk:  # Si création
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        """Optimiser les requêtes avec select_related"""
        return super().get_queryset(request).select_related(
            'ue', 'ue__filiere', 'ue__niveau', 'salle', 'surveillant', 'session', 'annee_academique'
        )


@admin.register(ControleAcces)
class ControleAccesAdmin(admin.ModelAdmin):
    """Administration des contrôles d'accès"""
    list_display = ('etudiant', 'examen', 'autorise', 'scan_method', 'date_scan', 'raison_courte')
    list_filter = ('autorise', 'scan_method', ('date_scan', DateTimeRangeFilter), 'examen__ue__filiere')
    search_fields = ('etudiant__matricule', 'etudiant__nom', 'examen__ue__code')
    actions = [exporter_csv]
    readonly_fields = ('date_scan', 'date_creation', 'date_modification', 'scanned_by', 'raison_refus')
    
    fieldsets = (
        ('Contrôle d\'accès', {
            'fields': ('examen', 'etudiant', 'scan_method', 'autorise')
        }),
        ('Détails', {
            'fields': ('raison_refus', 'date_scan')
        }),
        ('Traçabilité', {
            'fields': ('scanned_by', 'date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )
    
    def raison_courte(self, obj):
        """Afficher une version courte de la raison"""
        if obj.raison_refus:
            return obj.raison_refus[:50] + "..." if len(obj.raison_refus) > 50 else obj.raison_refus
        return ""
    raison_courte.short_description = "Raison (abrégée)"
    
    def save_model(self, request, obj, form, change):
        """Enregistrer l'utilisateur qui scanne"""
        if not obj.pk:  # Si création
            obj.scanned_by = request.user
        super().save_model(request, obj, form, change)
    
    def has_add_permission(self, request):
        """Empêcher l'ajout manuel (seuls les scans doivent créer)"""
        return False
    
    def get_queryset(self, request):
        """Optimiser les requêtes avec select_related"""
        return super().get_queryset(request).select_related(
            'etudiant', 'examen', 'examen__ue', 'scanned_by'
        )


@admin.register(JustificatifAbsence)
class JustificatifAbsenceAdmin(admin.ModelAdmin):
    """Administration des justificatifs d'absence"""
    list_display = ('etudiant', 'examen', 'type_justificatif', 'statut', 'date_depot', 'traite_par', 'fichier_lien')
    list_filter = ('statut', 'type_justificatif', 'examen__ue__filiere', ('date_depot', DateTimeRangeFilter))
    search_fields = ('etudiant__matricule', 'etudiant__nom', 'examen__ue__code')
    actions = [exporter_csv, 'accepter_justificatifs', 'refuser_justificatifs']
    readonly_fields = ('date_depot', 'date_creation', 'date_modification', 'fichier_lien')
    
    fieldsets = (
        ('Justificatif', {
            'fields': ('etudiant', 'examen', 'type_justificatif', 'description', 'fichier')
        }),
        ('Traitement', {
            'fields': ('statut', 'traite_par', 'commentaire_traitement', 'date_traitement')
        }),
        ('Dates', {
            'fields': ('date_depot', 'date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )
    
    def fichier_lien(self, obj):
        """Afficher un lien vers le fichier"""
        if obj.fichier:
            return format_html('<a href="{}" target="_blank">📄 Voir le fichier</a>', obj.fichier.url)
        return "Aucun fichier"
    fichier_lien.short_description = "Fichier"
    
    def accepter_justificatifs(self, request, queryset):
        """Accepter les justificatifs sélectionnés"""
        updated = queryset.filter(statut='en_attente').update(
            statut='accepte',
            traite_par=request.user,
            date_traitement=timezone.now()
        )
        self.message_user(request, f"{updated} justificatifs acceptés.")
    accepter_justificatifs.short_description = "Accepter les justificatifs"
    
    def refuser_justificatifs(self, request, queryset):
        """Refuser les justificatifs sélectionnés"""
        updated = queryset.filter(statut='en_attente').update(
            statut='refuse',
            traite_par=request.user,
            date_traitement=timezone.now()
        )
        self.message_user(request, f"{updated} justificatifs refusés.")
    refuser_justificatifs.short_description = "Refuser les justificatifs"
    
    def save_model(self, request, obj, form, change):
        """Gérer la date de traitement"""
        if obj.statut != 'en_attente' and not obj.date_traitement:
            obj.date_traitement = timezone.now()
            obj.traite_par = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        """Optimiser les requêtes avec select_related"""
        return super().get_queryset(request).select_related(
            'etudiant', 'examen', 'examen__ue', 'traite_par'
        )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Administration des logs d'audit"""
    list_display = ('timestamp', 'utilisateur', 'action_type', 'action_courte', 'ip')
    list_filter = ('action_type', ('timestamp', DateTimeRangeFilter))
    search_fields = ('utilisateur__username', 'action', 'ip')
    actions = [exporter_csv, 'vider_vieux_logs']
    readonly_fields = ('timestamp', 'utilisateur', 'action_type', 'action', 'details', 'ip', 'user_agent')
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Informations de log', {
            'fields': ('utilisateur', 'action_type', 'action', 'details')
        }),
        ('Informations techniques', {
            'fields': ('ip', 'user_agent', 'timestamp'),
            'classes': ('collapse',)
        }),
    )
    
    def action_courte(self, obj):
        """Afficher une version courte de l'action"""
        return obj.action[:100] + "..." if len(obj.action) > 100 else obj.action
    action_courte.short_description = "Action"
    
    def vider_vieux_logs(self, request, queryset):
        """Supprimer les logs de plus de 6 mois"""
        from datetime import timedelta
        limite = timezone.now() - timedelta(days=180)
        
        deleted_count, _ = AuditLog.objects.filter(timestamp__lt=limite).delete()
        self.message_user(request, f"{deleted_count} logs supprimés (avant {limite.date()}).")
    vider_vieux_logs.short_description = "Supprimer les logs de plus de 6 mois"
    
    def has_add_permission(self, request):
        """Empêcher l'ajout manuel"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Empêcher la modification"""
        return False
    
    def get_queryset(self, request):
        """Optimiser les requêtes avec select_related"""
        return super().get_queryset(request).select_related('utilisateur')


# ========================================================
# PERSONNALISATION DE L'ADMIN SITE
# ========================================================

admin.site.site_header = "Système de Gestion des Entrées en Salle d'Examen"
admin.site.site_title = "SGESE Admin"
admin.site.index_title = "Administration du système"

# Désinscrire le modèle Group si non utilisé
admin.site.unregister(Group)

# Ajouter des vues personnalisées si nécessaire
class DashboardAdmin(admin.AdminSite):
    site_header = "Tableau de bord - SGESE"
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_view(self.dashboard_view), name='dashboard'),
        ]
        return custom_urls + urls
    
    def dashboard_view(self, request):
        """Vue personnalisée pour le tableau de bord"""
        from django.shortcuts import render
        
        # Statistiques
        stats = {
            'total_etudiants': Etudiant.objects.count(),
            'etudiants_actifs': Etudiant.objects.filter(statut='actif').count(),
            'examens_aujourdhui': Examen.objects.filter(date=timezone.now().date()).count(),
            'scans_aujourdhui': ControleAcces.objects.filter(date_scan__date=timezone.now().date()).count(),
            'justificatifs_en_attente': JustificatifAbsence.objects.filter(statut='en_attente').count(),
        }
        
        context = {
            **self.each_context(request),
            'stats': stats,
            'title': 'Tableau de bord',
        }
        return render(request, 'admin/dashboard.html', context)

# Utiliser le site admin personnalisé si vous créez un AdminSite personnalisé
# admin_site = DashboardAdmin(name='monadmin')