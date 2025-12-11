from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action, permission_classes, api_view
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.views import APIView
from rest_framework.generics import RetrieveAPIView, ListAPIView
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count
from django.http import HttpResponse
from django.utils import timezone
import csv
from django.contrib.auth import authenticate, login
from .forms import UniversalLoginForm
import json
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.http import JsonResponse, HttpResponse
import qrcode
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView
from django.contrib.auth.forms import SetPasswordForm
import io
import base64
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from .forms import StudentLoginForm
from .forms import JustificatifForm
from datetime import timedelta

from .models import (
    Etudiant, Examen, ControleAcces, InscriptionUE,
    Paiement, JustificatifAbsence, UE, Salle, SessionExamen,
    AnneeAcademique, Filiere, Niveau, AuditLog
)
from .serializers import (
    EtudiantSerializer, ExamenSerializer, ControleAccesSerializer,
    JustificatifAbsenceSerializer, PaiementSerializer, InscriptionUESerializer,
    UESerializer, SalleSerializer, SessionExamenSerializer,
    AnneeAcademiqueSerializer, FiliereSerializer, NiveauSerializer,
    AuditLogSerializer, ScanSerializer, PresenceReportSerializer,
    StatistiquesSerializer, UserSerializer
)
from .permissions import (
    IsAdministrateur, IsSurveillant, IsEnseignant, IsResponsableScolarite,
    CanScanQRCode, CanManageExams, CanProcessJustificatif,
    IsOwnerOrAdmin, IsScanByUserOrAdmin, IsInSameFiliere
)
from .services import (
    QRCodeService, ExamenService, ScanService, ReportingService
)


# ========================================================
# VIEWSETS CRUD
# ========================================================

class AnneeAcademiqueViewSet(viewsets.ModelViewSet):
    """ViewSet pour les années académiques"""
    queryset = AnneeAcademique.objects.all()
    serializer_class = AnneeAcademiqueSerializer
    permission_classes = [IsAuthenticated, IsAdministrateur | IsResponsableScolarite]


class FiliereViewSet(viewsets.ModelViewSet):
    """ViewSet pour les filières"""
    queryset = Filiere.objects.all()
    serializer_class = FiliereSerializer
    permission_classes = [IsAuthenticated, IsAdministrateur | IsResponsableScolarite]
    search_fields = ['code', 'nom']


class NiveauViewSet(viewsets.ModelViewSet):
    """ViewSet pour les niveaux"""
    queryset = Niveau.objects.all()
    serializer_class = NiveauSerializer
    permission_classes = [IsAuthenticated, IsAdministrateur | IsResponsableScolarite]


class UEViewSet(viewsets.ModelViewSet):
    """ViewSet pour les Unités d'Enseignement"""
    queryset = UE.objects.all().select_related('filiere', 'niveau')
    serializer_class = UESerializer
    permission_classes = [IsAuthenticated, IsAdministrateur | IsResponsableScolarite | IsEnseignant]
    filterset_fields = ['filiere', 'niveau', 'semestre']
    search_fields = ['code', 'intitule']
    
    def get_queryset(self):
        """Filtrer par filière si l'utilisateur est enseignant"""
        queryset = super().get_queryset()
        
        if self.request.user.groups.filter(name='Enseignant').exists():
            # Filtrer les UE des filières de l'enseignant
            if hasattr(self.request.user, 'enseignant_profile'):
                filieres = self.request.user.enseignant_profile.filieres.all()
                queryset = queryset.filter(filiere__in=filieres)
        
        return queryset


class SalleViewSet(viewsets.ModelViewSet):
    """ViewSet pour les salles"""
    queryset = Salle.objects.all()
    serializer_class = SalleSerializer
    permission_classes = [IsAuthenticated, IsAdministrateur | IsResponsableScolarite]
    search_fields = ['code', 'batiment']


class SessionExamenViewSet(viewsets.ModelViewSet):
    """ViewSet pour les sessions d'examen"""
    queryset = SessionExamen.objects.all().select_related('annee_academique')
    serializer_class = SessionExamenSerializer
    permission_classes = [IsAuthenticated, IsAdministrateur | IsResponsableScolarite]
    filterset_fields = ['type_session', 'active', 'annee_academique']
    search_fields = ['nom']


class EtudiantViewSet(viewsets.ModelViewSet):
    """ViewSet pour les étudiants"""
    queryset = Etudiant.objects.all().select_related('filiere', 'niveau')
    serializer_class = EtudiantSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['filiere', 'niveau', 'statut']
    search_fields = ['matricule', 'nom', 'prenom', 'email']
    
    def get_permissions(self):
        """Permissions personnalisées selon l'action"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            self.permission_classes = [IsAdministrateur | IsResponsableScolarite]
        elif self.action in ['retrieve', 'list']:
            self.permission_classes = [IsAuthenticated]
        elif self.action == 'my_profile':
            self.permission_classes = [IsAuthenticated]
        
        return super().get_permissions()
    
    def get_queryset(self):
        """Filtrer le queryset selon les permissions"""
        queryset = super().get_queryset()
        
        # Si c'est un étudiant, ne voir que son propre profil
        if self.request.user.groups.filter(name='Etudiant').exists():
            if hasattr(self.request.user, 'etudiant_profile'):
                queryset = queryset.filter(id=self.request.user.etudiant_profile.id)
        
        # Si c'est un enseignant, ne voir que les étudiants de sa filière
        elif self.request.user.groups.filter(name='Enseignant').exists():
            if hasattr(self.request.user, 'enseignant_profile'):
                filieres = self.request.user.enseignant_profile.filieres.all()
                queryset = queryset.filter(filiere__in=filieres)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def my_profile(self, request):
        """Récupérer le profil de l'étudiant connecté"""
        if not hasattr(request.user, 'etudiant_profile'):
            return Response(
                {'error': 'Vous n\'êtes pas un étudiant'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        etudiant = request.user.etudiant_profile
        serializer = self.get_serializer(etudiant)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def qr_code(self, request, pk=None):
        """Générer le QR code d'un étudiant"""
        etudiant = self.get_object()
        
        # Vérifier les permissions
        if not (request.user.has_perm('gestion_examen.can_scan_qr') or 
                (hasattr(request.user, 'etudiant_profile') and 
                 request.user.etudiant_profile == etudiant)):
            return Response(
                {'error': 'Permission refusée'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        qr_data = QRCodeService.generate_qr_code(etudiant)
        return Response(qr_data)
    
    @action(detail=True, methods=['get'])
    def paiements(self, request, pk=None):
        """Récupérer les paiements d'un étudiant"""
        etudiant = self.get_object()
        
        # Vérifier les permissions
        if not (request.user.has_perm('gestion_examen.view_paiement') or 
                (hasattr(request.user, 'etudiant_profile') and 
                 request.user.etudiant_profile == etudiant)):
            return Response(
                {'error': 'Permission refusée'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        paiements = Paiement.objects.filter(etudiant=etudiant).select_related('annee_academique')
        serializer = PaiementSerializer(paiements, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def inscriptions(self, request, pk=None):
        """Récupérer les inscriptions d'un étudiant"""
        etudiant = self.get_object()
        
        # Vérifier les permissions
        if not (request.user.has_perm('gestion_examen.view_inscriptionue') or 
                (hasattr(request.user, 'etudiant_profile') and 
                 request.user.etudiant_profile == etudiant)):
            return Response(
                {'error': 'Permission refusée'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        inscriptions = InscriptionUE.objects.filter(etudiant=etudiant).select_related('ue', 'annee_academique')
        serializer = InscriptionUESerializer(inscriptions, many=True)
        return Response(serializer.data)


class ExamenViewSet(viewsets.ModelViewSet):
    """ViewSet pour les examens"""
    queryset = Examen.objects.all().select_related(
        'ue', 'ue__filiere', 'salle', 'surveillant', 'session', 'annee_academique'
    )
    serializer_class = ExamenSerializer
    permission_classes = [IsAuthenticated, CanManageExams | IsResponsableScolarite]
    filterset_fields = ['type_examen', 'session', 'ue__filiere', 'ue__niveau', 'date']
    search_fields = ['ue__code', 'ue__intitule', 'salle__code']
    
    def get_queryset(self):
        """Filtrer le queryset selon les permissions"""
        queryset = super().get_queryset()
        
        # Si c'est un surveillant, ne voir que ses examens
        if self.request.user.groups.filter(name='Surveillant').exists():
            queryset = queryset.filter(surveillant=self.request.user)
        
        # Si c'est un enseignant, ne voir que les examens de ses UE
        elif self.request.user.groups.filter(name='Enseignant').exists():
            if hasattr(self.request.user, 'enseignant_profile'):
                filieres = self.request.user.enseignant_profile.filieres.all()
                queryset = queryset.filter(ue__filiere__in=filieres)
        
        return queryset
    
    def perform_create(self, serializer):
        """Enregistrer l'utilisateur qui crée"""
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def scans(self, request, pk=None):
        """Récupérer les scans d'un examen"""
        examen = self.get_object()
        
        # Vérifier les permissions
        if not (request.user.has_perm('gestion_examen.view_controleacces') or 
                examen.surveillant == request.user):
            return Response(
                {'error': 'Permission refusée'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        scans = ScanService.get_scans_examen(pk, request.user)
        serializer = ControleAccesSerializer(scans, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def scanner(self, request, pk=None):
        """Scanner un étudiant pour cet examen"""
        examen = self.get_object()
        
        # Vérifier les permissions
        if not (request.user.has_perm('gestion_examen.can_scan_qr') or 
                examen.surveillant == request.user):
            return Response(
                {'error': 'Permission refusée'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ScanSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            result = ScanService.scanner_etudiant(pk, serializer.validated_data, request.user)
            
            # Si l'étudiant n'a pas été trouvé, retourner une erreur 404
            if result.get('etudiant') is None:
                return Response({
                    'success': False,
                    'message': 'Étudiant non trouvé',
                    'controle_id': result.get('controle_id')
                }, status=status.HTTP_404_NOT_FOUND)
                
            return Response(result)
            
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Erreur interne: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def rapport_presence(self, request, pk=None):
        """Générer un rapport de présence"""
        examen = self.get_object()
        
        # Vérifier les permissions
        if not (request.user.has_perm('gestion_examen.can_view_reports') or 
                examen.surveillant == request.user or
                (hasattr(request.user, 'enseignant_profile') and
                 request.user.enseignant_profile.filieres.filter(id=examen.ue.filiere.id).exists())):
            return Response(
                {'error': 'Permission refusée'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        rapport = ReportingService.generate_presence_report(pk)
        serializer = PresenceReportSerializer(rapport)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def export_presence_csv(self, request, pk=None):
        """Exporter le rapport de présence en CSV"""
        examen = self.get_object()
        
        # Vérifier les permissions
        if not (request.user.has_perm('gestion_examen.can_view_reports') or 
                examen.surveillant == request.user):
            return Response(
                {'error': 'Permission refusée'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        rapport = ReportingService.generate_presence_report(pk)
        
        # Créer la réponse CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="presence_{examen.ue.code}_{examen.date}.csv"'
        
        writer = csv.writer(response)
        
        # En-tête
        writer.writerow([f'Rapport de présence - {examen.ue.code} - {examen.date}'])
        writer.writerow([])
        writer.writerow(['Statistiques'])
        writer.writerow(['Total inscrits', rapport['statistiques']['total_inscrits']])
        writer.writerow(['Présents', rapport['statistiques']['total_presents']])
        writer.writerow(['Absents', rapport['statistiques']['total_absents']])
        writer.writerow(['Refusés', rapport['statistiques']['total_refuses']])
        writer.writerow(['Taux de présence', f"{rapport['statistiques']['taux_presence']}%"])
        writer.writerow([])
        writer.writerow(['Détail des présences'])
        writer.writerow(['Matricule', 'Nom', 'Prénom', 'Statut', 'Heure scan', 'Méthode', 'Raison'])
        
        # Données
        for presence in rapport['presences']:
            statut = 'PRESENT' if presence['present'] and presence['autorise'] else 'REFUSE' if presence['present'] else 'ABSENT'
            writer.writerow([
                presence['matricule'],
                presence['nom'],
                presence['prenom'],
                statut,
                presence['heure_scan'].strftime('%H:%M:%S') if presence['heure_scan'] else '',
                presence['methode_scan'] or '',
                presence['raison_refus'] or ''
            ])
        
        return response


class ControleAccesViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet en lecture seule pour les contrôles d'accès"""
    queryset = ControleAcces.objects.all().select_related(
        'etudiant', 'examen', 'examen__ue', 'scanned_by'
    )
    serializer_class = ControleAccesSerializer
    permission_classes = [IsAuthenticated, IsScanByUserOrAdmin | IsAdministrateur]
    filterset_fields = ['autorise', 'scan_method', 'examen', 'etudiant']
    
    def get_queryset(self):
        """Filtrer le queryset selon les permissions"""
        queryset = super().get_queryset()
        
        # Si c'est un surveillant, ne voir que ses scans
        if self.request.user.groups.filter(name='Surveillant').exists():
            queryset = queryset.filter(scanned_by=self.request.user)
        
        # Si c'est un enseignant, ne voir que les scans de sa filière
        elif self.request.user.groups.filter(name='Enseignant').exists():
            if hasattr(self.request.user, 'enseignant_profile'):
                filieres = self.request.user.enseignant_profile.filieres.all()
                queryset = queryset.filter(examen__ue__filiere__in=filieres)
        
        return queryset


class PaiementViewSet(viewsets.ModelViewSet):
    """ViewSet pour les paiements"""
    queryset = Paiement.objects.all().select_related('etudiant', 'annee_academique', 'created_by')
    serializer_class = PaiementSerializer
    permission_classes = [IsAuthenticated, IsResponsableScolarite | IsAdministrateur]
    filterset_fields = ['est_regle', 'annee_academique', 'etudiant']
    
    def perform_create(self, serializer):
        """Enregistrer l'utilisateur qui crée"""
        serializer.save(created_by=self.request.user)


class InscriptionUEViewSet(viewsets.ModelViewSet):
    """ViewSet pour les inscriptions UE"""
    queryset = InscriptionUE.objects.all().select_related('etudiant', 'ue', 'annee_academique', 'created_by')
    serializer_class = InscriptionUESerializer
    permission_classes = [IsAuthenticated, IsResponsableScolarite | IsAdministrateur]
    filterset_fields = ['est_autorise_examen', 'annee_academique', 'ue', 'etudiant']
    
    def perform_create(self, serializer):
        """Enregistrer l'utilisateur qui crée"""
        serializer.save(created_by=self.request.user)


class JustificatifAbsenceViewSet(viewsets.ModelViewSet):
    """ViewSet pour les justificatifs d'absence"""
    queryset = JustificatifAbsence.objects.all().select_related(
        'etudiant', 'examen', 'examen__ue', 'traite_par'
    )
    serializer_class = JustificatifAbsenceSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['statut', 'type_justificatif', 'examen', 'etudiant']
    
    def get_permissions(self):
        """Permissions personnalisées selon l'action"""
        if self.action in ['create']:
            self.permission_classes = [IsAuthenticated]
        elif self.action in ['update', 'partial_update', 'traitement']:
            self.permission_classes = [IsAuthenticated, CanProcessJustificatif]
        elif self.action in ['retrieve', 'list', 'mes_justificatifs']:
            self.permission_classes = [IsAuthenticated]
        
        return super().get_permissions()
    
    def get_queryset(self):
        """Filtrer le queryset selon les permissions"""
        queryset = super().get_queryset()
        
        # Si c'est un étudiant, ne voir que ses justificatifs
        if self.request.user.groups.filter(name='Etudiant').exists():
            if hasattr(self.request.user, 'etudiant_profile'):
                queryset = queryset.filter(etudiant=self.request.user.etudiant_profile)
        
        # Si c'est un enseignant, ne voir que les justificatifs de sa filière
        elif self.request.user.groups.filter(name='Enseignant').exists():
            if hasattr(self.request.user, 'enseignant_profile'):
                filieres = self.request.user.enseignant_profile.filieres.all()
                queryset = queryset.filter(examen__ue__filiere__in=filieres)
        
        return queryset
    
    def perform_create(self, serializer):
        """Associer l'étudiant connecté au justificatif"""
        if self.request.user.groups.filter(name='Etudiant').exists():
            if hasattr(self.request.user, 'etudiant_profile'):
                serializer.save(etudiant=self.request.user.etudiant_profile)
        else:
            serializer.save()
    
    @action(detail=False, methods=['get'])
    def mes_justificatifs(self, request):
        """Récupérer les justificatifs de l'étudiant connecté"""
        if not hasattr(request.user, 'etudiant_profile'):
            return Response(
                {'error': 'Vous n\'êtes pas un étudiant'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        justificatifs = self.get_queryset().filter(etudiant=request.user.etudiant_profile)
        serializer = self.get_serializer(justificatifs, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def traitement(self, request, pk=None):
        """Traiter un justificatif (accepter/refuser)"""
        justificatif = self.get_object()
        
        # Vérifier que le justificatif est en attente
        if justificatif.statut != 'en_attente':
            return Response(
                {'error': 'Ce justificatif a déjà été traité'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        statut = request.data.get('statut')
        commentaire = request.data.get('commentaire', '')
        
        if statut not in ['accepte', 'refuse']:
            return Response(
                {'error': 'Statut invalide. Valeurs autorisées: accepte, refuse'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        justificatif.statut = statut
        justificatif.commentaire_traitement = commentaire
        justificatif.traite_par = request.user
        justificatif.date_traitement = timezone.now()
        justificatif.save()
        
        serializer = self.get_serializer(justificatif)
        return Response(serializer.data)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet en lecture seule pour les logs d'audit"""
    queryset = AuditLog.objects.all().select_related('utilisateur')
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsAdministrateur]
    filterset_fields = ['action_type', 'utilisateur']
    search_fields = ['action', 'ip']
    ordering = ['-timestamp']


# ========================================================
# VUES SPÉCIFIQUES
# ========================================================

class DashboardView(APIView):
    """Vue pour le tableau de bord"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Récupérer les données du tableau de bord"""
        # Récupérer les examens du jour
        examens_du_jour = ExamenService.get_examens_du_jour(request.user)
        examens_serializer = ExamenSerializer(examens_du_jour, many=True, context={'request': request})
        
        # Statistiques selon le rôle
        if request.user.groups.filter(name='Surveillant').exists():
            # Statistiques pour surveillant
            mes_examens = examens_du_jour.filter(surveillant=request.user)
            scans_aujourdhui = ControleAcces.objects.filter(
                scanned_by=request.user,
                date_scan__date=timezone.now().date()
            ).count()
            
            stats = {
                'examens_aujourdhui': mes_examens.count(),
                'scans_aujourdhui': scans_aujourdhui,
                'role': 'surveillant'
            }
        
        elif request.user.groups.filter(name='Etudiant').exists():
            # Statistiques pour étudiant
            if hasattr(request.user, 'etudiant_profile'):
                etudiant = request.user.etudiant_profile
                examens_etudiant = Examen.objects.filter(
                    ue__inscriptionue__etudiant=etudiant,
                    ue__inscriptionue__est_autorise_examen=True,
                    date__gte=timezone.now().date()
                ).count()
                
                stats = {
                    'examens_a_venir': examens_etudiant,
                    'role': 'etudiant'
                }
            else:
                stats = {'role': 'etudiant'}
        
        elif request.user.groups.filter(name='Enseignant').exists():
            # Statistiques pour enseignant
            if hasattr(request.user, 'enseignant_profile'):
                filieres = request.user.enseignant_profile.filieres.all()
                examens_filiere = Examen.objects.filter(
                    ue__filiere__in=filieres,
                    date__gte=timezone.now().date()
                ).count()
                
                stats = {
                    'examens_filiere': examens_filiere,
                    'role': 'enseignant'
                }
            else:
                stats = {'role': 'enseignant'}
        
        elif request.user.groups.filter(name='Administrateur').exists() or request.user.is_superuser:
            # Statistiques pour administrateur
            stats = ReportingService.generate_statistiques_globales()
            stats['role'] = 'administrateur'
        
        else:
            stats = {'role': 'utilisateur'}
        
        return Response({
            'examens_du_jour': examens_serializer.data,
            'statistiques': stats,
            'user': UserSerializer(request.user, context={'request': request}).data
        })


class StatistiquesView(APIView):
    """Vue pour les statistiques détaillées"""
    permission_classes = [IsAuthenticated, IsAdministrateur | IsResponsableScolarite]
    
    def get(self, request):
        """Récupérer les statistiques"""
        annee_academique_id = request.query_params.get('annee_academique')
        
        stats = ReportingService.generate_statistiques_globales(annee_academique_id)
        serializer = StatistiquesSerializer(stats)
        
        return Response(serializer.data)


class ScanRapideView(APIView):
    """Vue pour le scan rapide (interface surveillant)"""
    permission_classes = [IsAuthenticated, CanScanQRCode]
    
    def get(self, request):
        """Récupérer les examens du surveillant pour aujourd'hui"""
        examens = ExamenService.get_examens_du_jour(request.user)
        
        # Formater pour l'interface de scan
        examens_data = []
        for examen in examens:
            if examen.surveillant == request.user or request.user.has_perm('gestion_examen.can_scan_qr'):
                examens_data.append({
                    'id': examen.id,
                    'ue': examen.ue.code,
                    'intitule': examen.ue.intitule,
                    'date': examen.date,
                    'heure_debut': examen.heure_debut,
                    'heure_fin': examen.heure_fin,
                    'salle': examen.salle.code if examen.salle else None,
                    'statistiques': ExamenService.get_statistiques_examen(examen)
                })
        
        return Response({'examens': examens_data})
    
    def post(self, request):
        """Scanner un étudiant (sans spécifier l'examen - détection automatique)"""
        serializer = ScanSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Trouver l'examen en cours pour ce surveillant
        maintenant = timezone.now()
        aujourdhui = maintenant.date()
        
        examen = Examen.objects.filter(
            surveillant=request.user,
            date=aujourdhui,
            heure_debut__lte=maintenant.time(),
            heure_fin__gte=maintenant.time()
        ).first()
        
        if not examen:
            return Response(
                {'error': 'Aucun examen en cours pour vous à cette heure'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            result = ScanService.scanner_etudiant(
                examen.id,
                serializer.validated_data,
                request.user
            )
            return Response(result)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# ========================================================
# VUES POUR L'AUTHENTIFICATION ET PROFIL
# ========================================================

class CurrentUserView(RetrieveAPIView):
    """Vue pour récupérer l'utilisateur connecté"""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    """Vue pour changer le mot de passe"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Changer le mot de passe"""
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        
        if not old_password or not new_password:
            return Response(
                {'error': 'Ancien et nouveau mot de passe requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not request.user.check_password(old_password):
            return Response(
                {'error': 'Ancien mot de passe incorrect'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        request.user.set_password(new_password)
        request.user.save()
        
        # Log l'action
        AuditLog.objects.create(
            utilisateur=request.user,
            action_type='system',
            action='Changement de mot de passe',
            ip=request.META.get('REMOTE_ADDR')
        )
        
        return Response({'message': 'Mot de passe changé avec succès'})


# ========================================================
# VUES PUBLIQUES (sans authentification)
# ========================================================

class VerifyQRCodeView(APIView):
    """Vue publique pour vérifier un QR code (pour applications externes)"""
    authentication_classes = []
    permission_classes = []
    
    def post(self, request):
        """Vérifier un QR code"""
        qr_data = request.data.get('qr_data')
        examen_id = request.data.get('examen_id')
        
        if not qr_data or not examen_id:
            return Response(
                {'error': 'qr_data et examen_id requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            examen = Examen.objects.get(id=examen_id)
        except Examen.DoesNotExist:
            return Response(
                {'error': 'Examen non trouvé'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            # Parser les données du QR code
            import json
            data = json.loads(qr_data)
            
            # Récupérer l'étudiant
            etudiant = Etudiant.objects.get(
                matricule=data['matricule'],
                qr_token=data['qr_token']
            )
            
            # Vérifications basiques
            if etudiant.statut != 'actif':
                return Response({
                    'valid': False,
                    'message': f"Étudiant {etudiant.get_statut_display()}"
                })
            
            # Vérifier l'inscription
            inscription = InscriptionUE.objects.filter(
                etudiant=etudiant,
                ue=examen.ue,
                annee_academique=examen.annee_academique,
                est_autorise_examen=True
            ).exists()
            
            if not inscription:
                return Response({
                    'valid': False,
                    'message': 'Non inscrit ou non autorisé'
                })
            
            return Response({
                'valid': True,
                'etudiant': {
                    'matricule': etudiant.matricule,
                    'nom': etudiant.nom,
                    'prenom': etudiant.prenom,
                    'photo_url': etudiant.photo.url if etudiant.photo else None
                }
            })
            
        except json.JSONDecodeError:
            return Response({
                'valid': False,
                'message': 'QR code invalide'
            })
        except Etudiant.DoesNotExist:
            return Response({
                'valid': False,
                'message': 'Étudiant non trouvé'
            })
        except Exception as e:
            return Response({
                'valid': False,
                'message': f'Erreur: {str(e)}'
            })





# core/views.py - Ajoutez ces vues
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import Etudiant, Examen, ControleAcces, JustificatifAbsence
from .services import ExamenService, ReportingService

# @login_required
# def dashboard_view(request):
#     """Vue du tableau de bord principal"""
#     context = {
#         'stats': {
#             'total_etudiants': Etudiant.objects.count(),
#             'examens_aujourdhui': Examen.objects.filter(date=timezone.now().date()).count(),
#             'scans_aujourdhui': ControleAcces.objects.filter(
#                 date_scan__date=timezone.now().date()
#             ).count(),
#             'examens_en_cours': Examen.objects.filter(
#                 date=timezone.now().date(),
#                 heure_debut__lte=timezone.now().time(),
#                 heure_fin__gte=timezone.now().time()
#             ).count(),
#         },
#         'examens_du_jour': ExamenService.get_examens_du_jour(request.user),
#         'recent_activity': [],  # À implémenter avec AuditLog
#     }
#     return render(request, 'core/dashboard.html', context)

@login_required
def scan_interface(request):
    """Interface de scan QR code"""
    examens = ExamenService.get_examens_du_jour(request.user)
    
    context = {
        'examens_disponibles': examens,
    }
    return render(request, 'core/scan_interface.html', context)

@login_required
def scan_examen(request, examen_id):
    """Interface de scan pour un examen spécifique"""
    examen = get_object_or_404(Examen, id=examen_id)
    
    # Vérifier les permissions
    if not (request.user.groups.filter(name='Surveillant').exists() or 
            examen.surveillant == request.user or 
            request.user.is_staff):
        messages.error(request, "Vous n'avez pas la permission de scanner cet examen.")
        return redirect('dashboard')
    
    context = {
        'examen': examen,
        'scans_recent': ControleAcces.objects.filter(
            examen=examen
        ).select_related('etudiant').order_by('-date_scan')[:10],
    }
    return render(request, 'core/scan_examen.html', context)

@login_required
def student_dashboard(request):
    """Tableau de bord étudiant"""
    if not hasattr(request.user, 'etudiant_profile'):
        messages.error(request, "Cette page est réservée aux étudiants.")
        return redirect('dashboard')
    
    etudiant = request.user.etudiant_profile
    
    context = {
        'etudiant': etudiant,
        'examens': Examen.objects.filter(
            ue__inscriptionue__etudiant=etudiant,
            ue__inscriptionue__est_autorise_examen=True
        ).select_related('ue', 'salle').order_by('date', 'heure_debut'),
        'paiements': etudiant.paiement_set.select_related('annee_academique'),
        'justificatifs': etudiant.justificatifabsence_set.select_related('examen', 'examen__ue'),
    }
    return render(request, 'core/student_dashboard.html', context)







@login_required
def change_password(request):
    """Changer le mot de passe"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important pour ne pas déconnecter l'utilisateur
            messages.success(request, 'Votre mot de passe a été changé avec succès!')
            
            # Log l'action
            from .models import AuditLog
            AuditLog.objects.create(
                utilisateur=request.user,
                action_type='system',
                action='Changement de mot de passe',
                details={'user_id': request.user.id},
                ip=request.META.get('REMOTE_ADDR')
            )
            
            return redirect('profile')
        else:
            messages.error(request, 'Veuillez corriger les erreurs ci-dessous.')
    else:
        form = PasswordChangeForm(request.user)
    
    context = {
        'form': form,
    }
    return render(request, 'core/change_password.html', context)




from django.shortcuts import render, redirect

def home_view(request):
    """Vue de la page d'accueil"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    context = {
        'app_name': 'SG Examens',
        'features': [
            {'icon': 'fa-qrcode', 'title': 'Scan QR Code', 'desc': 'Contrôle d\'accès rapide et sécurisé'},
            {'icon': 'fa-calendar-alt', 'title': 'Gestion des examens', 'desc': 'Planning et organisation simplifiés'},
            {'icon': 'fa-shield-alt', 'title': 'Sécurité renforcée', 'desc': 'Audit et traçabilité complète'},
            {'icon': 'fa-chart-line', 'title': 'Rapports détaillés', 'desc': 'Statistiques et analyses en temps réel'},
        ]
    }
    return render(request, 'core/home.html', context)




















































@login_required
def examen_list(request):
    """Liste des examens - MANQUANTE"""
    # Récupérer les examens selon le rôle
    if request.user.groups.filter(name='Surveillant').exists():
        examens = Examen.objects.filter(surveillant=request.user)
    elif request.user.groups.filter(name='Etudiant').exists():
        if hasattr(request.user, 'etudiant_profile'):
            etudiant = request.user.etudiant_profile
            examens = Examen.objects.filter(
                ue__inscriptionue__etudiant=etudiant,
                ue__inscriptionue__est_autorise_examen=True
            )
        else:
            examens = Examen.objects.none()
    else:
        # Administrateur/Enseignant/Résponsable - voir tous
        examens = Examen.objects.all()
    
    # Filtrer par date si demandé
    date_filter = request.GET.get('date')
    if date_filter:
        examens = examens.filter(date=date_filter)
    
    # Filtrer par filière si enseignant
    if request.user.groups.filter(name='Enseignant').exists():
        if hasattr(request.user, 'enseignant_profile'):
            filieres = request.user.enseignant_profile.filieres.all()
            examens = examens.filter(ue__filiere__in=filieres)
    
    examens = examens.select_related(
        'ue', 'ue__filiere', 'salle', 'surveillant', 'session'
    ).order_by('date', 'heure_debut')
    
    context = {
        'examens': examens,
        'today': timezone.now().date(),
        'date_filter': date_filter,
    }
    return render(request, 'core/examen_list.html', context)


@login_required
def examen_detail(request, pk):
    """Détail d'un examen - MANQUANTE"""
    examen = get_object_or_404(Examen.objects.select_related(
        'ue', 'ue__filiere', 'salle', 'surveillant', 'session', 'annee_academique'
    ), pk=pk)
    
    # Vérifier les permissions
    if request.user.groups.filter(name='Etudiant').exists():
        if hasattr(request.user, 'etudiant_profile'):
            if not InscriptionUE.objects.filter(
                etudiant=request.user.etudiant_profile,
                ue=examen.ue,
                est_autorise_examen=True
            ).exists():
                messages.error(request, "Vous n'êtes pas autorisé à voir cet examen.")
                return redirect('dashboard')
    
    elif request.user.groups.filter(name='Surveillant').exists():
        if examen.surveillant != request.user and not request.user.is_staff:
            messages.error(request, "Vous n'êtes pas surveillant de cet examen.")
            return redirect('dashboard')
    
    elif request.user.groups.filter(name='Enseignant').exists():
        if hasattr(request.user, 'enseignant_profile'):
            if examen.ue.filiere not in request.user.enseignant_profile.filieres.all():
                messages.error(request, "Cet examen n'est pas dans vos filières.")
                return redirect('dashboard')
    
    # Récupérer les statistiques
    stats = ExamenService.get_statistiques_examen(examen)
    
    # Récupérer les scans récents
    scans_recent = ControleAcces.objects.filter(
        examen=examen
    ).select_related('etudiant', 'scanned_by').order_by('-date_scan')[:20]
    
    # Récupérer les étudiants inscrits
    etudiants_inscrits = InscriptionUE.objects.filter(
        ue=examen.ue,
        annee_academique=examen.annee_academique,
        est_autorise_examen=True
    ).select_related('etudiant', 'etudiant__filiere')
    
    # Vérifier la présence de chaque étudiant
    etudiants_data = []
    for inscription in etudiants_inscrits:
        scan = ControleAcces.objects.filter(
            examen=examen,
            etudiant=inscription.etudiant
        ).first()
        
        etudiants_data.append({
            'etudiant': inscription.etudiant,
            'inscription': inscription,
            'scan': scan,
            'present': scan.autorise if scan else False,
            'autorise': scan.autorise if scan else False,
            'raison_refus': scan.raison_refus if scan else None
        })
    
    context = {
        'examen': examen,
        'stats': stats,
        'scans_recent': scans_recent,
        'etudiants_data': etudiants_data,
        'total_inscrits': len(etudiants_data),
    }
    return render(request, 'core/examen_detail.html', context)


@login_required
def examen_rapport(request, pk):
    """Rapport détaillé d'un examen - MANQUANTE"""
    examen = get_object_or_404(Examen, pk=pk)
    
    # Vérifier les permissions
    if not (request.user.groups.filter(name='Surveillant').exists() or 
            examen.surveillant == request.user or 
            request.user.is_staff or
            request.user.groups.filter(name='Enseignant').exists()):
        messages.error(request, "Vous n'avez pas la permission de voir ce rapport.")
        return redirect('dashboard')
    
    # Générer le rapport
    rapport = ReportingService.generate_presence_report(pk)
    
    context = {
        'examen': examen,
        'rapport': rapport,
    }
    return render(request, 'core/examen_rapport.html', context)


@login_required
def student_examens(request):
    """Page des examens de l'étudiant - MANQUANTE"""
    if not hasattr(request.user, 'etudiant_profile'):
        messages.error(request, "Cette page est réservée aux étudiants.")
        return redirect('dashboard')
    
    etudiant = request.user.etudiant_profile
    
    # Récupérer les examens à venir
    examens_a_venir = Examen.objects.filter(
        ue__inscriptionue__etudiant=etudiant,
        ue__inscriptionue__est_autorise_examen=True,
        date__gte=timezone.now().date()
    ).select_related('ue', 'salle', 'surveillant').order_by('date', 'heure_debut')
    
    # Récupérer les examens passés
    examens_passes = Examen.objects.filter(
        ue__inscriptionue__etudiant=etudiant,
        ue__inscriptionue__est_autorise_examen=True,
        date__lt=timezone.now().date()
    ).select_related('ue', 'salle').order_by('-date', 'heure_debut')[:20]
    
    # Vérifier les présences pour les examens à venir
    examens_avec_presence = []
    for examen in examens_a_venir:
        presence = ControleAcces.objects.filter(
            examen=examen,
            etudiant=etudiant,
            autorise=True
        ).first()
        
        justificatif = None
        if not presence:
            justificatif = examen.justificatifabsence_set.filter(
                etudiant=etudiant
            ).first()
        
        examens_avec_presence.append({
            'examen': examen,
            'est_present': presence is not None,
            'heure_scan': presence.date_scan if presence else None,
            'justificatif': justificatif,
            'statut_justificatif': justificatif.statut if justificatif else None
        })
    
    context = {
        'etudiant': etudiant,
        'examens_a_venir': examens_avec_presence,
        'examens_passes': examens_passes,
        'today': timezone.now().date(),
    }
    return render(request, 'core/student_examens.html', context)


@login_required
def student_qr(request):
    """Page pour afficher et télécharger le QR code de l'étudiant - MANQUANTE"""
    if not hasattr(request.user, 'etudiant_profile'):
        messages.error(request, "Cette page est réservée aux étudiants.")
        return redirect('dashboard')
    
    etudiant = request.user.etudiant_profile
    
    # Générer les données du QR code
    qr_data = {
        'matricule': etudiant.matricule,
        'qr_token': str(etudiant.qr_token),
        'nom': etudiant.nom,
        'prenom': etudiant.prenom,
        'timestamp': timezone.now().isoformat(),
        'filiere': etudiant.filiere.code if etudiant.filiere else None,
        'niveau': etudiant.niveau.nom if etudiant.niveau else None,
    }
    
    # Générer le QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(json.dumps(qr_data))
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convertir en base64 pour l'affichage
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    # Vérifier les examens où le QR code peut être utilisé
    examens_prochains = Examen.objects.filter(
        ue__inscriptionue__etudiant=etudiant,
        ue__inscriptionue__est_autorise_examen=True,
        date__gte=timezone.now().date()
    ).select_related('ue', 'salle').order_by('date', 'heure_debut')[:5]
    
    context = {
        'etudiant': etudiant,
        'qr_code': f"data:image/png;base64,{qr_base64}",
        'qr_data': json.dumps(qr_data, indent=2),
        'examens_prochains': examens_prochains,
        'qr_valid_until': timezone.now() + timezone.timedelta(minutes=30),
        'today': timezone.now().date(),
    }
    return render(request, 'core/student_qr.html', context)


@login_required
def download_qr(request):
    """Télécharger le QR code en PNG - MANQUANTE"""
    if not hasattr(request.user, 'etudiant_profile'):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Accès refusé")
    
    etudiant = request.user.etudiant_profile
    
    # Générer les données du QR code
    qr_data = {
        'matricule': etudiant.matricule,
        'qr_token': str(etudiant.qr_token),
        'nom': etudiant.nom,
        'prenom': etudiant.prenom,
        'timestamp': timezone.now().isoformat(),
    }
    
    # Générer le QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=15,
        border=4,
    )
    qr.add_data(json.dumps(qr_data))
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Créer la réponse
    from django.http import HttpResponse
    response = HttpResponse(content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="qr_code_{etudiant.matricule}.png"'
    
    img.save(response, 'PNG')
    return response


@login_required
def generate_qr_code_api(request):
    """API pour générer un nouveau QR code (rafraîchir) - MANQUANTE"""
    if not hasattr(request.user, 'etudiant_profile'):
        from django.http import JsonResponse
        return JsonResponse({'error': 'Accès refusé'}, status=403)
    
    etudiant = request.user.etudiant_profile
    
    # Générer les données du QR code
    qr_data = {
        'matricule': etudiant.matricule,
        'qr_token': str(etudiant.qr_token),
        'nom': etudiant.nom,
        'prenom': etudiant.prenom,
        'timestamp': timezone.now().isoformat(),
    }
    
    # Générer le QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(json.dumps(qr_data))
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convertir en base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    from django.http import JsonResponse
    return JsonResponse({
        'qr_code': f"data:image/png;base64,{qr_base64}",
        'qr_data': qr_data,
        'valid_until': (timezone.now() + timezone.timedelta(minutes=30)).isoformat(),
        'message': 'QR code généré avec succès'
    })


def documentation_view(request):
    """Page de documentation - MANQUANTE"""
    return render(request, 'core/documentation.html')


# ========================================================
# VUES EXISTANTES (que vous avez déjà)
# ========================================================

@login_required
def dashboard_view(request):
    """Vue du tableau de bord principal - EXISTANTE"""
    # Récupérer les statistiques
    stats = {
        'total_etudiants': Etudiant.objects.count(),
        'examens_aujourdhui': Examen.objects.filter(date=timezone.now().date()).count(),
        'scans_aujourdhui': ControleAcces.objects.filter(
            date_scan__date=timezone.now().date()
        ).count(),
        'examens_en_cours': Examen.objects.filter(
            date=timezone.now().date(),
            heure_debut__lte=timezone.now().time(),
            heure_fin__gte=timezone.now().time()
        ).count(),
    }
    
    # Récupérer les examens du jour
    examens_du_jour = ExamenService.get_examens_du_jour(request.user)
    
    # Récupérer l'activité récente
    recent_activity = AuditLog.objects.all().select_related('utilisateur').order_by('-timestamp')[:10]
    
    # Formater l'activité pour le template
    activity_data = []
    for activity in recent_activity:
        icon_map = {
            'scan': 'qrcode',
            'paiement': 'money-bill-wave',
            'inscription': 'user-plus',
            'examen': 'calendar-alt',
            'justificatif': 'file-medical',
            'system': 'cog',
            'connexion': 'sign-in-alt',
        }
        
        activity_data.append({
            'description': activity.action,
            'user': activity.utilisateur.get_full_name() if activity.utilisateur else "Système",
            'timestamp': activity.timestamp,
            'action_type': activity.action_type,
            'icon': icon_map.get(activity.action_type, 'info-circle'),
            'ip': activity.ip
        })
    
    context = {
        'stats': stats,
        'examens_du_jour': examens_du_jour,
        'recent_activity': activity_data,
    }
    return render(request, 'core/dashboard.html', context)


@login_required
def profile_view(request):
    """Page de profil utilisateur - EXISTANTE"""
    context = {
        'user': request.user,
    }
    
    if hasattr(request.user, 'etudiant_profile'):
        context['etudiant'] = request.user.etudiant_profile
    
    return render(request, 'core/profile.html', context)




@csrf_protect
def student_login_view(request):
    """Vue de connexion spécifique pour les étudiants"""
    # Si l'utilisateur est déjà authentifié, rediriger vers le dashboard
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = StudentLoginForm(request.POST)
        if form.is_valid():
            user = form.user
            login(request, user)
            
            # Log l'action
            AuditLog.objects.create(
                utilisateur=user,
                action_type='connexion',
                action='Connexion étudiant',
                details={'matricule': form.etudiant.matricule},
                ip=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            
            messages.success(request, f"Bienvenue {form.etudiant.nom} {form.etudiant.prenom} !")
            
            # Rediriger vers la page appropriée
            next_url = request.GET.get('next', 'student_dashboard')
            return redirect(next_url)
    else:
        form = StudentLoginForm()
    
    context = {
        'form': form,
        'title': 'Connexion Étudiant',
        'page': 'student_login'
    }
    return render(request, 'core/student_login.html', context)



class StudentPasswordResetView(PasswordResetView):
    """Réinitialisation de mot de passe pour étudiants"""
    template_name = 'registration/student_password_reset.html'
    email_template_name = 'registration/student_password_reset_email.html'
    subject_template_name = 'registration/student_password_reset_subject.txt'
    
    def form_valid(self, form):
        # Logique spécifique pour les étudiants
        # Vous pouvez vérifier si l'email correspond à un étudiant
        return super().form_valid(form)

class StudentPasswordResetConfirmView(PasswordResetConfirmView):
    """Confirmation de réinitialisation pour étudiants"""
    template_name = 'registration/student_password_reset_confirm.html'
    form_class = SetPasswordForm






@login_required
def add_justificatif(request, examen_id=None):
    """Ajouter un justificatif d'absence"""
    if not hasattr(request.user, 'etudiant_profile'):
        messages.error(request, "Cette fonctionnalité est réservée aux étudiants.")
        return redirect('dashboard')
    
    etudiant = request.user.etudiant_profile
    
    # Si un examen_id est fourni, pré-remplir l'examen
    examen = None
    if examen_id:
        examen = get_object_or_404(Examen, id=examen_id)
    
    if request.method == 'POST':
        form = JustificatifForm(request.POST, request.FILES)
        if form.is_valid():
            justificatif = form.save(commit=False)
            justificatif.etudiant = etudiant
            justificatif.save()
            
            messages.success(
                request, 
                "Votre justificatif a été soumis avec succès. "
                "Il sera traité par l'administration."
            )
            
            # Log l'action
            AuditLog.objects.create(
                utilisateur=request.user,
                action_type='justificatif',
                action=f'Justificatif soumis pour {justificatif.examen.ue.code}',
                details={
                    'justificatif_id': justificatif.id,
                    'examen_id': justificatif.examen.id,
                    'type': justificatif.type_justificatif
                },
                ip=request.META.get('REMOTE_ADDR')
            )
            
            return redirect('student_dashboard')
    else:
        initial = {}
        if examen:
            initial['examen'] = examen
        form = JustificatifForm(initial=initial)
    
    # Récupérer les examens auxquels l'étudiant est inscrit
    examens = Examen.objects.filter(
        ue__inscriptionue__etudiant=etudiant,
        ue__inscriptionue__est_autorise_examen=True,
        date__gte=timezone.now().date()  # Seulement les examens futurs
    ).select_related('ue', 'salle').order_by('date')
    
    context = {
        'form': form,
        'examens': examens,
        'etudiant': etudiant,
        'title': 'Ajouter un justificatif d\'absence'
    }
    
    return render(request, 'core/add_justificatif.html', context)






@csrf_protect
def universal_login_view(request):
    """Vue de connexion unique pour tous les types d'utilisateurs"""
    # Si déjà authentifié, rediriger
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UniversalLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            
            # Authentifier avec le backend personnalisé
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                if user.is_active:
                    login(request, user)
                    
                    # Déterminer la redirection selon le type d'utilisateur
                    if user.groups.filter(name='Etudiant').exists():
                        redirect_url = 'student_dashboard'
                        welcome_msg = f"Bienvenue {user.get_full_name()} !"
                    elif user.groups.filter(name='Surveillant').exists():
                        redirect_url = 'dashboard'
                        welcome_msg = f"Bienvenue Surveillant {user.get_full_name()} !"
                    elif user.groups.filter(name='Enseignant').exists():
                        redirect_url = 'dashboard'
                        welcome_msg = f"Bienvenue Professeur {user.get_full_name()} !"
                    elif user.is_staff or user.is_superuser:
                        redirect_url = 'dashboard'
                        welcome_msg = f"Bienvenue Administrateur {user.get_full_name()} !"
                    else:
                        redirect_url = 'dashboard'
                        welcome_msg = f"Bienvenue {user.get_full_name()} !"
                    
                    messages.success(request, welcome_msg)
                    
                    # Log l'action
                    AuditLog.objects.create(
                        utilisateur=user,
                        action_type='connexion',
                        action=f'Connexion réussie - {user.groups.first().name if user.groups.exists() else "Utilisateur"}',
                        details={'username': user.username},
                        ip=request.META.get('REMOTE_ADDR')
                    )
                    
                    next_url = request.GET.get('next', redirect_url)
                    return redirect(next_url)
                else:
                    messages.error(request, "Ce compte est désactivé.")
            else:
                messages.error(request, "Identifiants incorrects.")
    else:
        form = UniversalLoginForm()
    
    context = {
        'form': form,
        'title': 'Connexion',
        'show_student_option': True
    }
    return render(request, 'core/universal_login.html', context)