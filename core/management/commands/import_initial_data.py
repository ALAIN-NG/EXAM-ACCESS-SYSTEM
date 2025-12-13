# core/management/commands/import_initial_data.py
import os
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import random
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist

from core.models import (
    AnneeAcademique, Filiere, Niveau, UE, Etudiant,
    Paiement, InscriptionUE, Salle, SessionExamen, Examen
)


class Command(BaseCommand):
    help = 'Importe les données initiales depuis les fichiers CSV vers la base de données'
    
    # Noms des fichiers CSV (définis directement dans le code)
    FILIERES_FILE = 'FILIERES.csv'
    UE_FILE = 'UE.csv'
    ETUDIANTS_FILE = 'ETUDIANTS.csv'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Vider les tables avant import'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Début du chargement des données initiales...'))
        
        # Vider les tables si demandé
        if options['clear']:
            self.clear_tables()
        
        # Utiliser les noms de fichiers définis dans le code
        filieres_path = self.FILIERES_FILE
        ue_path = self.UE_FILE
        etudiants_path = self.ETUDIANTS_FILE
        
        self.stdout.write(f"📂 Recherche des fichiers CSV...")
        self.stdout.write(f"  - Filières: {filieres_path}")
        self.stdout.write(f"  - UEs: {ue_path}")
        self.stdout.write(f"  - Étudiants: {etudiants_path}")
        
        # Charger les fichiers CSV
        try:
            if not os.path.exists(filieres_path):
                raise FileNotFoundError(f"Fichier non trouvé: {filieres_path}")
            if not os.path.exists(ue_path):
                raise FileNotFoundError(f"Fichier non trouvé: {ue_path}")
            if not os.path.exists(etudiants_path):
                raise FileNotFoundError(f"Fichier non trouvé: {etudiants_path}")
            
            # Essayer différents encodages
            self.stdout.write("📖 Lecture des fichiers CSV...")
            
            # Lire les fichiers avec différents encodages
            filieres_df = self.read_csv_with_encoding(filieres_path)
            ue_df = self.read_csv_with_encoding(ue_path)
            etudiants_df = self.read_csv_with_encoding(etudiants_path)
            
            # Afficher un aperçu des données
            self.stdout.write(self.style.SUCCESS('✓ Fichiers CSV chargés avec succès'))
            self.stdout.write(f"  - Filières: {len(filieres_df)} lignes, {len(filieres_df.columns)} colonnes")
            self.stdout.write(f"  - UEs: {len(ue_df)} lignes, {len(ue_df.columns)} colonnes")
            self.stdout.write(f"  - Étudiants: {len(etudiants_df)} lignes, {len(etudiants_df.columns)} colonnes")
            
        except FileNotFoundError as e:
            self.stdout.write(self.style.ERROR(f"❌ {e}"))
            self.stdout.write(self.style.WARNING(f"📁 Répertoire courant: {os.getcwd()}"))
            self.stdout.write(self.style.WARNING(f"📁 Fichiers présents: {', '.join([f for f in os.listdir('.') if f.endswith('.csv')])}"))
            return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erreur de lecture CSV: {e}"))
            import traceback
            self.stdout.write(traceback.format_exc())
            return
        
        # Nettoyer les données
        try:
            self.stdout.write("\n🧹 Nettoyage des données...")
            filieres_df, ue_df, etudiants_df = self.clean_data(filieres_df, ue_df, etudiants_df)
            self.stdout.write(self.style.SUCCESS('✓ Données nettoyées'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erreur lors du nettoyage: {e}"))
            import traceback
            self.stdout.write(traceback.format_exc())
            return
        
        # Exécuter dans une transaction
        try:
            with transaction.atomic():
                # 1. Année académique
                annee_academique = self.create_annee_academique()
                if not annee_academique:
                    raise Exception("Impossible de créer l'année académique")
                
                # 2. Niveaux
                self.create_niveaux()
                
                # 3. Filieres
                filiere_mapping = self.create_filieres(filieres_df)
                
                # 4. UEs
                ue_mapping = self.create_ues(ue_df, filiere_mapping)
                
                # 5. Étudiants
                etudiant_mapping = self.create_etudiants(etudiants_df, filiere_mapping)
                
                # 6. Salles (30 salles)
                salles = self.create_salles()
                
                # 7. Sessions d'examen
                sessions = self.create_session_examen(annee_academique)
                
                # 8. Utilisateurs supplémentaires
                self.create_users_supplementaires()
                
                # 9. Paiements (mixte)
                self.create_paiements(etudiant_mapping, annee_academique)
                
                # 10. Inscriptions UE
                self.create_inscriptions_ues(etudiant_mapping, ue_mapping, annee_academique)
                
                # 11. Examens pour TOUTES les UEs
                if sessions and salles:
                    self.create_examens(ue_mapping, annee_academique, sessions, salles)
                
                self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
                self.stdout.write(self.style.SUCCESS('✅ CHARGEMENT DES DONNÉES TERMINÉ AVEC SUCCÈS!'))
                self.stdout.write(self.style.SUCCESS('=' * 60))
                
                # Afficher le résumé
                self.print_summary()
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erreur lors de l'import: {e}"))
            import traceback
            self.stdout.write(traceback.format_exc())
            self.stdout.write(self.style.WARNING("⏪ Rollback de la transaction en cours..."))
    
    def read_csv_with_encoding(self, file_path):
        """Lit un fichier CSV en essayant différents encodages"""
        encodings = ['utf-8', 'latin-1', 'ISO-8859-1', 'cp1252', 'utf-8-sig']
        
        for encoding in encodings:
            try:
                df = pd.read_csv(file_path, encoding=encoding)
                return df
            except UnicodeDecodeError:
                continue
            except Exception as e:
                self.stdout.write(f"⚠️  Erreur avec l'encodage {encoding} pour {file_path}: {e}")
                continue
        
        # Si aucun encodage ne fonctionne, essayer sans spécifier d'encodage
        try:
            df = pd.read_csv(file_path)
            return df
        except Exception as e:
            raise Exception(f"Impossible de lire le fichier {file_path} avec aucun encodage: {e}")
    
    def clear_tables(self):
        """Vide les tables avant import"""
        self.stdout.write(self.style.WARNING('⚠️  Vidage des tables existantes...'))
        models = [Paiement, InscriptionUE, Examen, Etudiant, UE, Salle, SessionExamen, Filiere, Niveau, AnneeAcademique]
        
        for model in models:
            try:
                count = model.objects.count()
                if count > 0:
                    model.objects.all().delete()
                    self.stdout.write(self.style.WARNING(f"  - {model.__name__}: {count} enregistrements supprimés"))
                else:
                    self.stdout.write(f"  - {model.__name__}: déjà vide")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  - {model.__name__}: erreur lors de la suppression - {e}"))
    
    def clean_data(self, filieres_df, ue_df, etudiants_df):
        """Nettoie et prépare les données"""
        # Afficher les colonnes originales
        self.stdout.write(f"  Colonnes Filières: {list(filieres_df.columns)}")
        self.stdout.write(f"  Colonnes UEs: {list(ue_df.columns)}")
        self.stdout.write(f"  Colonnes Étudiants: {list(etudiants_df.columns)}")
        
        # Nettoyer les noms de colonnes (supprimer les espaces)
        filieres_df.columns = [col.strip() for col in filieres_df.columns]
        ue_df.columns = [col.strip() for col in ue_df.columns]
        etudiants_df.columns = [col.strip() for col in etudiants_df.columns]
        
        # Normaliser les noms de colonnes (minuscules)
        filieres_df.columns = [col.lower() for col in filieres_df.columns]
        ue_df.columns = [col.lower() for col in ue_df.columns]
        etudiants_df.columns = [col.lower() for col in etudiants_df.columns]
        
        # Standardiser les noms de colonnes pour UE
        column_mapping = {}
        
        # Mapper les colonnes existantes
        for col in ue_df.columns:
            col_lower = col.lower()
            if 'code' in col_lower:
                column_mapping[col] = 'code'
            elif 'nitit' in col_lower or 'intit' in col_lower or 'titre' in col_lower:
                column_mapping[col] = 'intitule'
            elif 'silver' in col_lower or 'filiere' in col_lower:
                column_mapping[col] = 'filiere'
            elif 'inver' in col_lower or 'niveau' in col_lower:
                column_mapping[col] = 'niveau'
            elif 'semestre' in col_lower:
                column_mapping[col] = 'semestre'
            elif 'sperol' in col_lower:
                column_mapping[col] = 'sperol'
        
        if column_mapping:
            ue_df = ue_df.rename(columns=column_mapping)
        
        # Nettoyer les valeurs pour UE
        if 'semestre' in ue_df.columns:
            ue_df['semestre'] = ue_df['semestre'].astype(str).str.extract(r'(\d+)')
            ue_df['semestre'] = pd.to_numeric(ue_df['semestre'], errors='coerce')
        
        if 'niveau' in ue_df.columns:
            ue_df['niveau'] = ue_df['niveau'].astype(str).str.replace('L', '').str.strip()
            ue_df['niveau'] = pd.to_numeric(ue_df['niveau'], errors='coerce')
        
        if 'filiere' in ue_df.columns:
            ue_df['filiere'] = ue_df['filiere'].astype(str).str.strip()
        
        # Pour les étudiants, créer des emails et téléphones par défaut si non présents
        if 'email' not in etudiants_df.columns and 'matricule' in etudiants_df.columns:
            etudiants_df['email'] = etudiants_df['matricule'].astype(str) + '@univ.local'
        
        if 'telephone' not in etudiants_df.columns:
            etudiants_df['telephone'] = '+237600000000'
        
        return filieres_df, ue_df, etudiants_df
    
    def create_annee_academique(self):
        """Crée une année académique par défaut"""
        try:
            annee, created = AnneeAcademique.objects.get_or_create(
                code='2023-2024',
                defaults={'active': True}
            )
            status = 'Créée' if created else 'Existe déjà'
            self.stdout.write(self.style.SUCCESS(f"📅 Année académique: {status}"))
            return annee
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erreur lors de la création de l'année académique: {e}"))
            return None
    
    def create_niveaux(self):
        """Crée les niveaux L1, L2, L3, M1, M2"""
        niveaux = [
            {'nom': 'L1', 'ordre': 1},
            {'nom': 'L2', 'ordre': 2},
            {'nom': 'L3', 'ordre': 3},
            {'nom': 'M1', 'ordre': 4},
            {'nom': 'M2', 'ordre': 5},
        ]
        
        created_count = 0
        for niveau_data in niveaux:
            try:
                obj, created = Niveau.objects.get_or_create(
                    nom=niveau_data['nom'],
                    defaults={'ordre': niveau_data['ordre']}
                )
                if created:
                    created_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Erreur lors de la création du niveau {niveau_data['nom']}: {e}"))
        
        self.stdout.write(self.style.SUCCESS(f"📚 Niveaux créés: {created_count}/{len(niveaux)}"))
    
    def create_filieres(self, filieres_df):
        """Crée les filières à partir du dataframe"""
        created_count = 0
        filiere_mapping = {}
        
        # Déterminer les noms de colonnes
        nom_col = None
        code_col = None
        
        for col in filieres_df.columns:
            col_lower = col.lower()
            if 'list' in col_lower or 'nom' in col_lower or 'name' in col_lower:
                nom_col = col
            elif 'abrev' in col_lower or 'code' in col_lower or 'abr' in col_lower:
                code_col = col
        
        if not nom_col or not code_col:
            # Essayer avec les premières colonnes
            if len(filieres_df.columns) >= 2:
                nom_col = filieres_df.columns[0]
                code_col = filieres_df.columns[1]
        
        for _, row in filieres_df.iterrows():
            try:
                nom_filiere = str(row[nom_col]).strip() if nom_col else 'Filière inconnue'
                code_filiere = str(row[code_col]).strip() if code_col else 'CODE'
                
                if not nom_filiere or nom_filiere == 'nan':
                    self.stdout.write(self.style.WARNING(f"⚠️  Nom de filière manquant pour la ligne: {row.to_dict()}"))
                    continue
                
                if not code_filiere or code_filiere == 'nan':
                    code_filiere = nom_filiere[:3].upper()
                
                # Créer ou récupérer la filière
                filiere, created = Filiere.objects.get_or_create(
                    code=code_filiere,
                    defaults={'nom': nom_filiere}
                )
                
                if created:
                    created_count += 1
                
                # Stocker le mapping pour référence ultérieure
                filiere_mapping[nom_filiere.upper()] = filiere
                filiere_mapping[code_filiere] = filiere
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Erreur lors de la création de la filière {row.to_dict()}: {e}"))
        
        self.stdout.write(self.style.SUCCESS(f"🎓 Filieres créées: {created_count}"))
        return filiere_mapping
    
    def create_ues(self, ue_df, filiere_mapping):
        """Crée les UEs à partir du dataframe"""
        created_count = 0
        ue_mapping = {}
        
        # Mapping des noms de filière abrégés
        filiere_name_mapping = {
            'PHYSIQUE': 'RHY',
            'CHIMIE': 'CUM',
            'MATHEMATIQUE': 'MAT',
            'INFORMATIQUE': 'INF',
            'GEOSCIENCES': 'GEOS',
            'BIOCHIMIE': 'BCH',
            'BIOLOGIE ET PHYSIOLOGIE ANIMALE': 'BOA',
            'BIOLOGIE ET PHYSIOLOGIE VEGETALE': 'BOV',
            'BIOSCIENCES': 'BIOS',
            'MICROBIOLOGIE': 'MIB',
            'CHIMIE ORGANIQUE': 'CQ',
            'CHIMIE INORGANIQUE': 'CI',
        }
        
        for _, row in ue_df.iterrows():
            try:
                # Extraire les valeurs
                code = str(row.get('code', '')).strip()
                intitule = str(row.get('intitule', '')).strip()
                filiere_nom = str(row.get('filiere', '')).strip()
                niveau_num = row.get('niveau')
                semestre = row.get('semestre')
                
                # Si certaines valeurs sont manquantes, essayer d'autres noms de colonnes
                if not code:
                    for col in row.index:
                        if 'code' in col.lower():
                            code = str(row[col]).strip()
                            break
                
                if not intitule:
                    for col in row.index:
                        if 'nitit' in col.lower() or 'intit' in col.lower():
                            intitule = str(row[col]).strip()
                            break
                
                if not filiere_nom or pd.isna(filiere_nom):
                    for col in row.index:
                        if 'silver' in col.lower() or 'filiere' in col.lower():
                            filiere_nom = str(row[col]).strip()
                            break
                
                if pd.isna(niveau_num):
                    for col in row.index:
                        if 'inver' in col.lower() or 'niveau' in col.lower():
                            niveau_num = row[col]
                            break
                
                if pd.isna(semestre):
                    for col in row.index:
                        if 'semestre' in col.lower():
                            semestre = row[col]
                            break
                
                # Validation des données requises
                if not code:
                    self.stdout.write(self.style.WARNING(f"⚠️  Code manquant pour la ligne UE: {row.to_dict()}"))
                    continue
                
                if not intitule:
                    intitule = f"UE {code}"
                
                if not filiere_nom or pd.isna(filiere_nom) or filiere_nom == 'nan':
                    self.stdout.write(self.style.WARNING(f"⚠️  Filière manquante pour l'UE {code}"))
                    continue
                
                if pd.isna(niveau_num):
                    niveau_num = 1
                
                if pd.isna(semestre):
                    semestre = 1
                
                # Trouver la filière correspondante
                filiere = None
                
                # Essayer de trouver la filière directement
                for key, f in filiere_mapping.items():
                    if isinstance(key, str) and key.upper() in filiere_nom.upper():
                        filiere = f
                        break
                
                # Si non trouvé, essayer avec le mapping
                if not filiere:
                    for key in filiere_name_mapping:
                        if key in filiere_nom.upper():
                            code_abrev = filiere_name_mapping[key]
                            if code_abrev in filiere_mapping:
                                filiere = filiere_mapping[code_abrev]
                                break
                
                if not filiere:
                    self.stdout.write(self.style.WARNING(f"⚠️  Filière non trouvée pour {filiere_nom} (UE: {code})"))
                    if filiere_mapping:
                        filiere = list(filiere_mapping.values())[0]
                    else:
                        continue
                
                # Trouver le niveau correspondant
                try:
                    niveau_num_int = int(float(niveau_num))
                    niveau, _ = Niveau.objects.get_or_create(
                        nom=f"L{niveau_num_int}",
                        defaults={'ordre': niveau_num_int}
                    )
                except (ValueError, TypeError):
                    niveau, _ = Niveau.objects.get_or_create(
                        nom='L1',
                        defaults={'ordre': 1}
                    )
                
                # Créer ou mettre à jour l'UE
                ue, created = UE.objects.get_or_create(
                    code=code,
                    filiere=filiere,
                    defaults={
                        'intitule': intitule,
                        'niveau': niveau,
                        'semestre': int(semestre),
                        'credit': 6
                    }
                )
                
                if not created:
                    ue.intitule = intitule
                    ue.niveau = niveau
                    ue.semestre = int(semestre)
                    ue.save()
                
                if created:
                    created_count += 1
                
                ue_mapping[code] = ue
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Erreur lors de la création de l'UE: {e}"))
        
        self.stdout.write(self.style.SUCCESS(f"📖 UEs créées: {created_count}"))
        return ue_mapping
    
    def create_etudiants(self, etudiants_df, filiere_mapping):
        """Crée les étudiants à partir du dataframe"""
        created_count = 0
        etudiant_mapping = {}
        
        # Mapping des codes de filière basés sur le matricule
        code_filiere_map = {
            'B': 'BCH', 'C': 'CUM', 'D': 'BOV', 'E': 'BOA',
            'F': 'GEOS', 'G': 'INF', 'H': 'RHY', 'I': 'MAT',
            'J': 'MIB', 'K': 'CQ', 'L': 'CI', 'M': 'BIOS'
        }
        
        # Déterminer les colonnes
        matricule_col = None
        nom_col = None
        prenom_col = None
        email_col = None
        telephone_col = None
        
        for col in etudiants_df.columns:
            col_lower = col.lower()
            if 'matricule' in col_lower:
                matricule_col = col
            elif 'nom' in col_lower and 'prenom' not in col_lower:
                nom_col = col
            elif 'prenom' in col_lower:
                prenom_col = col
            elif 'email' in col_lower or 'mail' in col_lower:
                email_col = col
            elif 'telephone' in col_lower or 'phone' in col_lower or 'tel' in col_lower:
                telephone_col = col
        
        # Si non trouvé, utiliser les premières colonnes
        if not matricule_col and len(etudiants_df.columns) > 0:
            matricule_col = etudiants_df.columns[0]
        if not nom_col and len(etudiants_df.columns) > 1:
            nom_col = etudiants_df.columns[1]
        if not prenom_col and len(etudiants_df.columns) > 2:
            prenom_col = etudiants_df.columns[2]
        
        for _, row in etudiants_df.iterrows():
            try:
                matricule = str(row[matricule_col]).strip() if matricule_col else ''
                nom = str(row[nom_col]).strip() if nom_col else ''
                prenom = str(row[prenom_col]).strip() if prenom_col else ''
                email = str(row[email_col]).strip() if email_col else ''
                telephone = str(row[telephone_col]).strip() if telephone_col else ''
                
                if not matricule or not nom or not prenom:
                    self.stdout.write(self.style.WARNING(f"⚠️  Données manquantes pour l'étudiant: {row.to_dict()}"))
                    continue
                
                # Déterminer la filière basée sur le code de matricule
                filiere = None
                niveau = None
                
                # Extraire le code filière du matricule (ex: 22C422 -> C)
                if len(matricule) >= 3:
                    code_char = matricule[2].upper()
                    if code_char in code_filiere_map:
                        code_filiere = code_filiere_map[code_char]
                        filiere = filiere_mapping.get(code_filiere)
                
                # Si non trouvé, prendre une filière aléatoire
                if not filiere and filiere_mapping:
                    filiere = random.choice(list(filiere_mapping.values()))
                
                # Déterminer le niveau basé sur l'année du matricule
                try:
                    annee_matricule = int(matricule[:2])
                    if annee_matricule in [21, 22]:
                        niveau_num = random.choice([1, 2])
                        niveau, _ = Niveau.objects.get_or_create(
                            nom=f'L{niveau_num}',
                            defaults={'ordre': niveau_num}
                        )
                    else:
                        niveau, _ = Niveau.objects.get_or_create(
                            nom='L1',
                            defaults={'ordre': 1}
                        )
                except:
                    niveau, _ = Niveau.objects.get_or_create(
                        nom='L1',
                        defaults={'ordre': 1}
                    )
                
                # Créer l'email si non fourni
                if not email:
                    email = f"{matricule}@univ.local"
                
                # Créer le téléphone si non fourni
                if not telephone:
                    telephone = f'+2376{random.randint(10000000, 99999999)}'
                
                # Créer ou mettre à jour l'étudiant
                etudiant, created = Etudiant.objects.get_or_create(
                    matricule=matricule,
                    defaults={
                        'nom': nom,
                        'prenom': prenom,
                        'email': email,
                        'telephone': telephone,
                        'filiere': filiere,
                        'niveau': niveau,
                        'statut': 'actif'
                    }
                )
                
                if not created:
                    etudiant.nom = nom
                    etudiant.prenom = prenom
                    etudiant.email = email
                    etudiant.telephone = telephone
                    etudiant.filiere = filiere
                    etudiant.niveau = niveau
                    etudiant.save()
                
                if created:
                    created_count += 1
                
                etudiant_mapping[matricule] = etudiant
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Erreur lors de la création de l'étudiant {row.get('matricule', 'N/A')}: {e}"))
        
        self.stdout.write(self.style.SUCCESS(f"👥 Étudiants créés: {created_count}"))
        return etudiant_mapping
    
    def create_salles(self):
        """Crée 30 salles différentes"""
        salles = []
        batiments = ['BAT_A', 'BAT_B', 'BAT_C', 'BAT_D', 'BAT_E']
        etages = ['RDC', '1ER', '2EME', '3EME']
        
        for i in range(1, 31):
            salle_data = {
                'code': f'SALLE_{i:02d}',
                'capacite': random.randint(30, 120),
                'batiment': random.choice(batiments),
                'etage': random.choice(etages)
            }
            salles.append(salle_data)
        
        created_count = 0
        salle_objects = []
        
        for salle_data in salles:
            try:
                obj, created = Salle.objects.get_or_create(
                    code=salle_data['code'],
                    defaults=salle_data
                )
                if created:
                    created_count += 1
                salle_objects.append(obj)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Erreur lors de la création de la salle {salle_data['code']}: {e}"))
        
        self.stdout.write(self.style.SUCCESS(f"🏫 Salles créées: {created_count}/30"))
        return salle_objects
    
    def create_session_examen(self, annee_academique):
        """Crée deux sessions d'examen (normale et rattrapage)"""
        sessions = []
        
        # Session normale (commence dans 2 semaines)
        date_debut_normale = datetime.now() + timedelta(days=14)
        date_fin_normale = date_debut_normale + timedelta(days=21)
        
        # Session rattrapage (commence 1 mois après la fin de la session normale)
        date_debut_rattrapage = date_fin_normale + timedelta(days=14)
        date_fin_rattrapage = date_debut_rattrapage + timedelta(days=14)
        
        session_data = [
            {
                'nom': 'Session Normale 2023-2024',
                'type_session': 'normale',
                'date_debut': date_debut_normale.date(),
                'date_fin': date_fin_normale.date(),
                'active': True
            },
            {
                'nom': 'Session Rattrapage 2023-2024',
                'type_session': 'rattrapage',
                'date_debut': date_debut_rattrapage.date(),
                'date_fin': date_fin_rattrapage.date(),
                'active': False
            }
        ]
        
        created_count = 0
        session_objects = []
        
        for data in session_data:
            try:
                session, created = SessionExamen.objects.get_or_create(
                    nom=data['nom'],
                    annee_academique=annee_academique,
                    defaults=data
                )
                
                if created:
                    created_count += 1
                session_objects.append(session)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Erreur lors de la création de la session {data['nom']}: {e}"))
        
        self.stdout.write(self.style.SUCCESS(f"📝 Sessions d'examen créées: {created_count}/2"))
        return session_objects
    
    def create_users_supplementaires(self):
        """Crée des utilisateurs supplémentaires pour les surveillants"""
        users = [
            {'username': 'admin', 'email': 'admin@univ.local', 'password': 'admin123',
             'first_name': 'Admin', 'last_name': 'System', 'is_superuser': True, 'is_staff': True},
            {'username': 'surv1', 'email': 'surv1@univ.local', 'password': 'surv123',
             'first_name': 'Paul', 'last_name': 'Martin'},
            {'username': 'surv2', 'email': 'surv2@univ.local', 'password': 'surv123',
             'first_name': 'Marie', 'last_name': 'Dubois'},
            {'username': 'surv3', 'email': 'surv3@univ.local', 'password': 'surv123',
             'first_name': 'Pierre', 'last_name': 'Durand'},
            {'username': 'surv4', 'email': 'surv4@univ.local', 'password': 'surv123',
             'first_name': 'Sophie', 'last_name': 'Leroy'},
        ]
        
        created_count = 0
        for user_data in users:
            try:
                # Extraire les champs spécifiques
                is_superuser = user_data.pop('is_superuser', False)
                is_staff = user_data.pop('is_staff', False)
                password = user_data.pop('password')
                
                user, created = User.objects.get_or_create(
                    username=user_data['username'],
                    defaults=user_data
                )
                
                if created:
                    user.set_password(password)
                    user.is_superuser = is_superuser
                    user.is_staff = is_staff
                    user.save()
                    created_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Erreur lors de la création de l'utilisateur {user_data.get('username', 'N/A')}: {e}"))
        
        self.stdout.write(self.style.SUCCESS(f"👤 Utilisateurs supplémentaires créés: {created_count}/{len(users)}"))
    
    def create_paiements(self, etudiants_mapping, annee_academique):
        """Crée les paiements avec statut mixte (certains payés, d'autres non)"""
        created_count = 0
        
        for i, (matricule, etudiant) in enumerate(etudiants_mapping.items()):
            try:
                # Alterner les statuts de paiement
                est_regle = i % 3 != 0  # 2/3 des étudiants ont payé
                
                if est_regle:
                    montant = 50000  # Paiement complet
                    date_paiement = datetime.now() - timedelta(days=random.randint(1, 30))
                else:
                    # Certains ont payé partiellement, d'autres rien
                    if random.choice([True, False]):
                        montant = random.randint(10000, 40000)  # Paiement partiel
                        date_paiement = datetime.now() - timedelta(days=random.randint(1, 30))
                    else:
                        montant = 0  # Pas payé du tout
                        date_paiement = None
                
                paiement, created = Paiement.objects.get_or_create(
                    etudiant=etudiant,
                    annee_academique=annee_academique,
                    defaults={
                        'montant_attendu': 50000,
                        'montant': montant,
                        'est_regle': est_regle,
                        'date_paiement': date_paiement
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    # Si le paiement existe déjà, mettre à jour le statut
                    paiement.montant = montant
                    paiement.est_regle = est_regle
                    paiement.date_paiement = date_paiement
                    paiement.save()
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Erreur lors de la création du paiement pour {matricule}: {e}"))
        
        # Afficher les statistiques
        total_paiements = Paiement.objects.count()
        paiements_regles = Paiement.objects.filter(est_regle=True).count()
        paiements_partiels = Paiement.objects.filter(montant__gt=0, est_regle=False).count()
        
        self.stdout.write(self.style.SUCCESS(f"💰 Paiements créés: {created_count}"))
        self.stdout.write(self.style.SUCCESS(f"  - Total: {total_paiements}"))
        self.stdout.write(self.style.SUCCESS(f"  - Réglés complètement: {paiements_regles}"))
        self.stdout.write(self.style.SUCCESS(f"  - Partiels: {paiements_partiels}"))
        self.stdout.write(self.style.SUCCESS(f"  - Non réglés: {total_paiements - paiements_regles - paiements_partiels}"))
    
    def create_inscriptions_ues(self, etudiants_mapping, ue_mapping, annee_academique):
        """Crée les inscriptions aux UEs pour les étudiants"""
        created_count = 0
        
        # Créer un utilisateur admin pour les created_by
        try:
            admin_user = User.objects.filter(is_superuser=True).first()
        except:
            admin_user = None
        
        for matricule, etudiant in etudiants_mapping.items():
            try:
                # Vérifier si l'étudiant a payé pour déterminer s'il est autorisé
                paiement = Paiement.objects.filter(
                    etudiant=etudiant,
                    annee_academique=annee_academique
                ).first()
                
                est_autorise = paiement.est_regle if paiement else False
                
                # Inscrire l'étudiant aux UEs de sa filière et son niveau
                ues_inscrire = UE.objects.filter(
                    filiere=etudiant.filiere,
                    niveau=etudiant.niveau
                )
                
                for ue in ues_inscrire:
                    try:
                        inscription, created = InscriptionUE.objects.get_or_create(
                            etudiant=etudiant,
                            ue=ue,
                            annee_academique=annee_academique,
                            defaults={
                                'est_autorise_examen': est_autorise,
                                'created_by': admin_user
                            }
                        )
                        
                        if created:
                            created_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"⚠️  Erreur inscription {matricule} à {ue.code}: {e}"))
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Erreur lors des inscriptions pour {matricule}: {e}"))
        
        # Afficher les statistiques
        total_inscriptions = InscriptionUE.objects.count()
        autorisees = InscriptionUE.objects.filter(est_autorise_examen=True).count()
        
        self.stdout.write(self.style.SUCCESS(f"📝 Inscriptions UE créées: {created_count}"))
        self.stdout.write(self.style.SUCCESS(f"  - Total: {total_inscriptions}"))
        self.stdout.write(self.style.SUCCESS(f"  - Autorisées pour examen: {autorisees}"))
        self.stdout.write(self.style.SUCCESS(f"  - Non autorisées: {total_inscriptions - autorisees}"))
    
    def create_examens(self, ue_mapping, annee_academique, sessions, salles):
        """Crée des examens pour TOUTES les UEs à partir d'aujourd'hui"""
        created_count = 0
        
        # Récupérer un surveillant
        try:
            surveillant = User.objects.filter(username='surv1').first()
        except:
            surveillant = None
        
        # Organiser les UEs par filière et niveau pour regrouper les examens
        ues_par_filiere_niveau = {}
        
        for ue in ue_mapping.values():
            key = (ue.filiere.id, ue.niveau.id, ue.semestre)
            if key not in ues_par_filiere_niveau:
                ues_par_filiere_niveau[key] = []
            ues_par_filiere_niveau[key].append(ue)
        
        # Dates d'examen (commencent demain et s'étalent sur 3 semaines)
        date_courante = datetime.now() + timedelta(days=1)
        jours_examens = 0
        max_jours_examens = 21  # 3 semaines
        
        # Heures d'examen possibles
        creneaux_horaires = [
            (time(8, 0), time(10, 0)),   # 8h-10h
            (time(10, 30), time(12, 30)), # 10h30-12h30
            (time(14, 0), time(16, 0)),   # 14h-16h
            (time(16, 30), time(18, 30)), # 16h30-18h30
        ]
        
        # Créer des examens pour chaque groupe d'UEs
        for (filiere_id, niveau_id, semestre), ues_groupe in ues_par_filiere_niveau.items():
            # S'assurer qu'on ne dépasse pas la période d'examen
            if jours_examens >= max_jours_examens:
                break
            
            # Pour chaque UE dans le groupe
            for i, ue in enumerate(ues_groupe):
                try:
                    # Choisir un créneau horaire (alterner pour éviter les conflits)
                    heure_debut, heure_fin = creneaux_horaires[i % len(creneaux_horaires)]
                    
                    # Choisir une salle aléatoire
                    salle = random.choice(salles)
                    
                    # Choisir une session (normale pour la plupart, rattrapage pour quelques-uns)
                    session = sessions[0] if random.random() > 0.2 else sessions[1]
                    
                    examen, created = Examen.objects.get_or_create(
                        ue=ue,
                        annee_academique=annee_academique,
                        session=session,
                        date=date_courante.date(),
                        heure_debut=heure_debut,
                        defaults={
                            'heure_fin': heure_fin,
                            'type_examen': session.type_session,
                            'salle': salle,
                            'surveillant': surveillant
                        }
                    )
                    
                    if created:
                        created_count += 1
                    else:
                        # Mettre à jour si existe déjà
                        examen.heure_fin = heure_fin
                        examen.salle = salle
                        examen.surveillant = surveillant
                        examen.save()
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"❌ Erreur lors de la création de l'examen pour {ue.code}: {e}"))
            
            # Passer au jour suivant après avoir programmé toutes les UEs d'un groupe
            if ues_groupe:
                # Avancer à la date du prochain jour ouvrable (sauter les weekends)
                date_courante += timedelta(days=1)
                while date_courante.weekday() >= 5:  # 5 = Samedi, 6 = Dimanche
                    date_courante += timedelta(days=1)
                jours_examens += 1
        
        # Afficher les statistiques
        self.stdout.write(self.style.SUCCESS(f"📋 Examens créés: {created_count}"))
        
        # Vérifier si des examens ont été créés
        if Examen.objects.exists():
            premier_examen = Examen.objects.order_by('date', 'heure_debut').first()
            dernier_examen = Examen.objects.order_by('-date', '-heure_fin').first()
            
            if premier_examen and dernier_examen:
                self.stdout.write(self.style.SUCCESS(f"  - Dates: de {premier_examen.date} à {dernier_examen.date}"))
                self.stdout.write(self.style.SUCCESS(f"  - Salles utilisées: {len(set(Examen.objects.values_list('salle', flat=True)))}"))
                
                # Répartition par session
                examens_normaux = Examen.objects.filter(type_examen='normal').count()
                examens_rattrapage = Examen.objects.filter(type_examen='rattrapage').count()
                self.stdout.write(self.style.SUCCESS(f"  - Session normale: {examens_normaux}"))
                self.stdout.write(self.style.SUCCESS(f"  - Session rattrapage: {examens_rattrapage}"))
        else:
            self.stdout.write(self.style.WARNING(f"  - Aucun examen créé"))
    
    def print_summary(self):
        """Affiche un résumé des données importées"""
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('📊 RÉSUMÉ FINAL')
        self.stdout.write('=' * 60)
        self.stdout.write(f"📅 Années académiques: {AnneeAcademique.objects.count()}")
        self.stdout.write(f"📚 Niveaux: {Niveau.objects.count()}")
        self.stdout.write(f"🎓 Filieres: {Filiere.objects.count()}")
        self.stdout.write(f"📖 UEs: {UE.objects.count()}")
        self.stdout.write(f"👥 Étudiants: {Etudiant.objects.count()}")
        
        paiements_total = Paiement.objects.count()
        paiements_regles = Paiement.objects.filter(est_regle=True).count()
        self.stdout.write(f"💰 Paiements: {paiements_total} ({paiements_regles} réglés)")
        
        inscriptions_total = InscriptionUE.objects.count()
        inscriptions_autorisees = InscriptionUE.objects.filter(est_autorise_examen=True).count()
        self.stdout.write(f"📝 Inscriptions UE: {inscriptions_total} ({inscriptions_autorisees} autorisées)")
        
        self.stdout.write(f"🏫 Salles: {Salle.objects.count()}")
        self.stdout.write(f"📋 Sessions examen: {SessionExamen.objects.count()}")
        self.stdout.write(f"📝 Examens: {Examen.objects.count()}")
        self.stdout.write(f"👤 Utilisateurs: {User.objects.count()}")
        self.stdout.write('=' * 60)
        
        # Aperçu des prochains examens
        examens_prochains = Examen.objects.filter(
            date__gte=datetime.now().date()
        ).order_by('date', 'heure_debut')[:5]
        
        if examens_prochains.exists():
            self.stdout.write('\n📅 PROCHAINS EXAMENS:')
            for examen in examens_prochains:
                self.stdout.write(f"  - {examen.ue.code}: {examen.date} {examen.heure_debut}-{examen.heure_fin} ({examen.salle.code})")
        
        # Informations de connexion
        self.stdout.write('\n🔑 INFORMATIONS DE CONNEXION:')
        admin_user = User.objects.filter(is_superuser=True).first()
        if admin_user:
            self.stdout.write(f"  - Admin: username='{admin_user.username}' password='admin123'")
        
        surveillant = User.objects.filter(username='surv1').first()
        if surveillant:
            self.stdout.write(f"  - Surveillant: username='{surveillant.username}' password='surv123'")
        
        self.stdout.write('\n🎉 Les données sont prêtes! Vous pouvez maintenant accéder à l\'application.')