#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Warframe Prime Drop Analyzer
Analyse les drop rates officiels de Warframe pour trouver les meilleures missions de farm
"""

import sys
import io

# Force UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import requests
from bs4 import BeautifulSoup  # type: ignore
import re
from collections import defaultdict
from typing import List, Dict, Tuple
import warnings

# Supprime les avertissements SSL
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# URL officielle des droptables
DROPTABLES_URL = "https://warframe-web-assets.nyc3.cdn.digitaloceanspaces.com/uploads/cms/hnfvc0o3jnfvc873njb03enrf56.html"


class WarframeDropAnalyzer:
    """Analyseur de drops Warframe"""
    
    def __init__(self):
        self.html_content = None
        self.soup = None
        
    def fetch_droptables(self):
        """Récupère le contenu HTML des droptables officielles"""
        print(f"📥 Récupération des droptables depuis {DROPTABLES_URL}...")
        try:
            # Désactive la vérification SSL si nécessaire (uniquement pour ce site officiel)
            response = requests.get(DROPTABLES_URL, timeout=30, verify=False)
            response.raise_for_status()
            self.html_content = response.text
            self.soup = BeautifulSoup(self.html_content, 'html.parser')
            print("✅ Droptables récupérées avec succès!\n")
            return True
        except Exception as e:
            print(f"❌ Erreur lors de la récupération: {e}")
            return False
    
    def find_item_in_relics(self, item_name: str) -> Dict[str, Dict]:
        """
        Trouve toutes les reliques contenant un item donné
        Retourne un dict {nom_relique: {'reward_mentions': X, 'drop_mentions': Y}}
        """
        print(f"🔍 Recherche de '{item_name}' dans les reliques...")
        
        # Compte les mentions de chaque relique
        relic_data = defaultdict(lambda: {'reward_mentions': 0, 'drop_mentions': 0})
        
        # Cherche toutes les lignes contenant l'item
        text = self.soup.get_text()
        lines = text.split('\n')
        
        # Première passe : compter les mentions dans les tableaux de récompenses des reliques
        for line in lines:
            if item_name in line:
                # Extrait le nom de la relique si présent (format: "Lith X1 Relic (Intact)")
                relic_match = re.search(r'(Lith|Meso|Neo|Axi)\s+([A-Z]\d+)\s+Relic\s+\((Intact|Exceptional|Flawless|Radiant)\)', line)
                if relic_match:
                    relic_name = f"{relic_match.group(1)} {relic_match.group(2)}"
                    relic_data[relic_name]['reward_mentions'] += 1
        
        # Deuxième passe : compter combien de fois chaque relique apparaît comme drop (avec son nom + "Relic")
        for relic_name in relic_data.keys():
            search_pattern = f"{relic_name} Relic"
            for line in lines:
                # Ne compte que si c'est une ligne de drop (contient un pourcentage)
                if search_pattern in line and '%' in line and not re.search(r'\((Intact|Exceptional|Flawless|Radiant)\)', line):
                    relic_data[relic_name]['drop_mentions'] += 1
        
        if relic_data:
            print(f"✅ Trouvé dans {len(relic_data)} relique(s):\n")
            for relic, data in sorted(relic_data.items()):
                reward_count = data['reward_mentions']
                drop_count = data['drop_mentions']
                
                # Une relique est vaultée si elle a 4 mentions de récompense mais 0 drop
                if reward_count == 4 and drop_count == 0:
                    status = "🔒 VAULTED"
                else:
                    status = f"✅ ACTIF ({drop_count} missions)"
                
                print(f"  • {relic}: {status}")
        else:
            print(f"❌ '{item_name}' non trouvé dans les reliques")
        
        return dict(relic_data)
    
    def is_relic_vaulted(self, relic_data: Dict) -> bool:
        """
        Détermine si une relique est vaultée
        Une relique vaultée a 4 reward_mentions mais 0 drop_mentions
        """
        return relic_data['reward_mentions'] == 4 and relic_data['drop_mentions'] == 0
    
    def find_relic_farm_locations(self, relic_name: str) -> List[Dict[str, str]]:
        """
        Trouve tous les endroits où farmer une relique avec les taux de drop
        Retourne une liste de dicts avec: mission, planète, type, rotation, drop_rate
        """
        print(f"\n🗺️  Recherche des lieux de farm pour '{relic_name} Relic'...")
        
        farm_locations = []
        text = self.soup.get_text()
        
        # Le HTML colle tout sur une ligne, on doit chercher autrement
        # Pattern: Planète/Mission (Type)...Rotation X...Nom RelicRarity (X.XX%)
        # Exemple dans le texte: "Mercury/Suisei (Spy)Rotation A...Rotation BLith A10 RelicUncommon (14.29%)"
        
        # Découpe par mission (cherche les patterns Planète/Mission (Type))
        mission_pattern = r'([^/\n]+)/([^\(\n]+)\s*\(([^\)]+)\)'
        missions = re.split(mission_pattern, text)
        
        # Parcours les missions trouvées
        for i in range(1, len(missions), 4):  # Les groupes capturés sont à i, i+1, i+2, le contenu à i+3
            if i+3 >= len(missions):
                break
                
            planet = missions[i].strip()
            mission = missions[i+1].strip()
            mission_type = missions[i+2].strip()
            content = missions[i+3]
            
            # Ignore certaines sections (pas de vraies missions)
            if planet in ['Relics', 'Event', 'Baro']:
                continue
            
            # Cherche la relique dans le contenu de cette mission
            # Pattern: Rotation X...Nom RelicRarity (X.XX%)
            # On divise par rotation
            rotations = re.split(r'Rotation ([ABC])', content)
            
            current_rotation = None
            for j, part in enumerate(rotations):
                # Les rotations sont aux indices impairs
                if j % 2 == 1:
                    current_rotation = part.strip()
                    continue
                
                # Cherche la relique dans cette partie
                # Pattern: "Lith A10 Relic" suivi de "Uncommon (14.29%)" ou "Rare (X.XX%)" etc
                relic_full_name = f"{relic_name} Relic"
                if relic_full_name in part:
                    # Extrait le taux de drop qui suit immédiatement
                    # Format: "Lith A10 RelicUncommon (14.29%)" (sans espace!)
                    pattern = rf'{re.escape(relic_full_name)}(Rare|Uncommon|Common|Very Common)\s*\(([0-9.]+)%\)'
                    matches = re.finditer(pattern, part)
                    
                    for match in matches:
                        rarity = match.group(1)
                        drop_rate = float(match.group(2))
                        
                        location = {
                            'mission': mission,
                            'planet': planet,
                            'type': mission_type,
                            'rotation': current_rotation if current_rotation else 'Reward',
                            'rarity': rarity,
                            'drop_rate': drop_rate
                        }
                        farm_locations.append(location)
        
        if farm_locations:
            print(f"✅ Trouvé {len(farm_locations)} lieu(x) de farm\n")
        else:
            print(f"❌ Aucun lieu de farm trouvé (relique probablement vaultée)\n")
        
        return farm_locations
    
    def configure_mission_filters(self, available_missions: List[dict] = None) -> List[str]:
        """
        Configure les filtres de missions à exclure des résultats
        
        Args:
            available_missions: Liste des missions disponibles pour extraire les types
            
        Returns:
            Liste des patterns à exclure (planets, mission types)
        """
        print("\n" + "=" * 60)
        print("🔍 CONFIGURATION DES FILTRES")
        print("=" * 60)
        print("Voulez-vous exclure certaines missions des résultats?\n")
        
        choice = input("Appliquer des filtres? (o/n): ").strip().lower()
        
        if choice not in ['o', 'oui', 'y', 'yes']:
            return []
        
        # Extrait les types de missions disponibles
        if available_missions:
            mission_types = sorted(set(m['type'] for m in available_missions))
            planets = sorted(set(m['planet'] for m in available_missions))
            
            print("\n🎯 TYPES DE MISSIONS DISPONIBLES:")
            for i, mtype in enumerate(mission_types, 1):
                print(f"  {i}. {mtype}")
            
            print("\n🌍 PLANÈTES/ZONES DISPONIBLES:")
            planet_chunks = [planets[i:i+5] for i in range(0, len(planets), 5)]
            for chunk in planet_chunks:
                print(f"  {', '.join(chunk)}")
        else:
            print("Types de missions courants:")
            print("  • Spy (Espionnage)")
            print("  • Defense, Survival, Interception, Excavation")
            print("  • Assassination, Capture, Exterminate")
            print("\nPlanètes/zones spéciales:")
            print("  • Duviri (The Circuit, etc.)")
            print("  • Event (missions événementielles)")
            print("  • Void, Lua, Kuva Fortress")
        
        excluded = []
        print("\nEntrez les termes à exclure (séparés par des virgules)")
        print("Exemples: 'Duviri, Spy' ou 'Event, Defense'")
        print("Laissez vide pour ne rien exclure.\n")
        
        filters_input = input("Filtres: ").strip()
        
        if filters_input:
            excluded = [f.strip() for f in filters_input.split(',')]
            print(f"\n✅ Filtres appliqués: {', '.join(excluded)}")
        
        return excluded
    
    def get_prime_components(self, base_name: str) -> List[str]:
        """
        Détecte tous les composants d'un item Prime selon le type d'équipement
        
        Args:
            base_name: Nom de base (ex: 'Gauss Prime', 'Acceltra Prime')
            
        Returns:
            Liste des composants trouvés dans les reliques
        """
        print("\n" + "=" * 60)
        print("🔧 TYPE D'ÉQUIPEMENT")
        print("=" * 60)
        print("1️⃣  Warframe")
        print("2️⃣  Arme Primary (fusil, arc, etc.)")
        print("3️⃣  Arme Melee (épée, hache, etc.)")
        print("4️⃣  Arme Secondary (pistolet, kunai, etc.)")
        print()
        
        while True:
            try:
                choice = input("Choisissez le type (1-4): ").strip()
                
                if choice == '1':
                    parts = ['Blueprint', 'Chassis Blueprint', 'Neuroptics Blueprint', 'Systems Blueprint']
                    break
                elif choice == '2':
                    # Primary: Stock/Barrel/Receiver (Acceltra Prime)
                    parts = ['Blueprint', 'Stock', 'Barrel', 'Receiver']
                    break
                elif choice == '3':
                    # Melee: Blade/Hilt (Nikana Prime) ou Blade/Handle/Guard (autres)
                    # On teste d'abord Blade/Hilt, puis Blade/Handle/Guard
                    test_parts = [f"{base_name} Blade", f"{base_name} Hilt"]
                    if all(self.find_item_in_relics(p) for p in test_parts):
                        parts = ['Blueprint', 'Blade', 'Hilt']
                    else:
                        parts = ['Blueprint', 'Blade', 'Handle', 'Guard']
                    break
                elif choice == '4':
                    # Secondary: Barrel/Receiver (Kompressa Prime) - PAS de Link
                    parts = ['Blueprint', 'Barrel', 'Receiver']
                    break
                else:
                    print("❌ Choix invalide. Entrez 1, 2, 3 ou 4.")
            except (KeyboardInterrupt, EOFError):
                print("\n⚠️  Opération annulée")
                return []
        
        # Cherche les composants avec le pattern sélectionné
        valid_parts = []
        for part in parts:
            component_name = f"{base_name} {part}"
            relics = self.find_item_in_relics(component_name)
            if relics:
                valid_parts.append(component_name)
        
        return valid_parts
    
    def find_mod_in_missions(self, mod_name: str) -> List[dict]:
        """
        Trouve toutes les missions qui droppent un mod spécifique
        
        Args:
            mod_name: Nom du mod (ex: 'Serration', 'Steel Fiber')
            
        Returns:
            Liste des missions avec taux de drop
        """
        if not self.soup:
            print("⚠️  Les droptables n'ont pas été chargées")
            return []
        
        missions_text = str(self.soup)
        
        # Pattern pour trouver les missions
        mission_pattern = r'([^/\n]+)/([^\(\n]+)\s*\(([^\)]+)\)'
        missions = re.split(mission_pattern, missions_text)
        
        farm_locations = []
        
        for i in range(1, len(missions), 4):
            if i+3 > len(missions):
                break
            
            planet = missions[i].strip()
            mission = missions[i+1].strip()
            mission_type = missions[i+2].strip()
            content = missions[i+3]
            
            # Ignore certaines sections
            if planet in ['Relics', 'Event', 'Baro', 'Rotation']:
                continue
            
            # Cherche le mod dans le contenu avec rotation
            rotation_pattern = r'Rotation ([ABC])'
            rotations = re.split(rotation_pattern, content)
            
            for rot_idx in range(1, len(rotations), 2):
                if rot_idx+1 > len(rotations):
                    break
                
                rotation_letter = rotations[rot_idx]
                rotation_content = rotations[rot_idx+1]
                
                # Cherche le mod avec son taux de drop et sa rareté
                mod_pattern = rf'{re.escape(mod_name)}\s*\|\s*(Very Common|Common|Uncommon|Rare|Ultra Rare|Legendary)\s*\(([0-9.]+)%\)'
                mod_match = re.search(mod_pattern, rotation_content, re.IGNORECASE)
                
                if mod_match:
                    rarity = mod_match.group(1)
                    drop_rate = float(mod_match.group(2))
                    
                    farm_locations.append({
                        'planet': planet,
                        'mission': mission,
                        'type': mission_type,
                        'rotation': f"Rot. {rotation_letter}",
                        'drop_rate': drop_rate,
                        'rarity': rarity
                    })
        
        return farm_locations
    
    def analyze_mod(self, mod_name: str):
        """
        Analyse complète d'un mod avec ses meilleurs lieux de farm
        """
        print("=" * 80)
        print(f"🔧 ANALYSE DU MOD: {mod_name}")
        print("=" * 80 + "\n")
        
        # Trouve toutes les missions
        all_missions = self.find_mod_in_missions(mod_name)
        
        if not all_missions:
            print(f"\n⚠️  Mod '{mod_name}' non trouvé dans les droptables")
            print("Vérifiez l'orthographe exacte du mod.")
            return
        
        # Configuration des filtres avec la liste des missions disponibles
        filters = self.configure_mission_filters(all_missions)
        
        # Applique les filtres
        missions = self.apply_mission_filters(all_missions, filters)
        
        if not missions:
            print("\n⚠️  Toutes les missions ont été exclues par les filtres")
            return
        
        # Trie par taux de drop décroissant
        missions.sort(key=lambda x: x['drop_rate'], reverse=True)
        
        print(f"\n📋 {len(missions)} MISSIONS TROUVÉES (triées par drop rate):\n")
        print(f"{'#':<4} {'Drop%':<8} {'Mission':<30} {'Planète':<20} {'Type':<15} {'Rotation':<10}")
        print("-" * 110)
        
        for idx, farm in enumerate(missions, 1):
            print(f"{idx:<4} {farm['drop_rate']:<8.2f} {farm['mission']:<30} {farm['planet']:<20} "
                  f"{farm['type']:<15} {farm['rotation']:<10}")
        
        # Résumé des meilleures missions
        print("\n" + "=" * 80)
        print("⭐ TOP 5 MISSIONS RECOMMANDÉES")
        print("=" * 80 + "\n")
        
        for idx, farm in enumerate(missions[:5], 1):
            print(f"{idx}. 🎯 {farm['mission']} ({farm['planet']})")
            print(f"   Type: {farm['type']}")
            print(f"   Rotation: {farm['rotation']}")
            print(f"   Drop rate: {farm['drop_rate']}% ({farm['rarity']})")
            print()
        
        print("=" * 80)
        print("✅ ANALYSE TERMINÉE")
        print("=" * 80 + "\n")
    
    def analyze_prime_item(self, item_name: str, show_header: bool = True):
        """
        Analyse complète d'un item Prime
        Trouve les reliques, identifie celles qui sont actives, et liste les meilleurs endroits de farm
        """
        if show_header:
            print("=" * 80)
            print(f"🎯 ANALYSE DE: {item_name}")
            print("=" * 80 + "\n")
        
        # Étape 1: Trouver les reliques
        relics = self.find_item_in_relics(item_name)
        
        if not relics:
            print("\n⚠️  Aucune relique trouvée. Vérifiez le nom de l'item.")
            return
        
        # Étape 2: Pour chaque relique, vérifier si elle est vaultée
        print("\n" + "=" * 80)
        print("📊 ANALYSE DES RELIQUES")
        print("=" * 80)
        
        active_relics = []
        vaulted_relics = []
        
        for relic, data in relics.items():
            if self.is_relic_vaulted(data):
                vaulted_relics.append(relic)
            else:
                active_relics.append(relic)
        
        print(f"\n✅ Reliques ACTIVES: {len(active_relics)}")
        for relic in active_relics:
            print(f"   • {relic}")
        
        print(f"\n🔒 Reliques VAULTED: {len(vaulted_relics)}")
        for relic in vaulted_relics:
            print(f"   • {relic}")
        
        # Étape 3: Pour chaque relique active, trouver les lieux de farm
        if active_relics:
            print("\n" + "=" * 80)
            print("🗺️  MEILLEURS ENDROITS DE FARM")
            print("=" * 80)
            
            all_farms = []
            
            for relic in active_relics:
                farms = self.find_relic_farm_locations(relic)
                for farm in farms:
                    farm['relic'] = relic
                    all_farms.append(farm)
            
            if all_farms:
                # Configuration des filtres avec la liste des missions disponibles
                filters = []
                if show_header:
                    filters = self.configure_mission_filters(all_farms)
                
                # Applique les filtres si configurés
                if filters:
                    all_farms = self.apply_mission_filters(all_farms, filters)
                
                # Agrège les missions identiques (même mission/rotation avec plusieurs reliques)
                all_farms = self.aggregate_mission_drops(all_farms)
                
                # Trier par taux de drop décroissant
                all_farms.sort(key=lambda x: x['drop_rate'], reverse=True)
                
                print(f"\n📋 {len(all_farms)} MISSIONS TROUVÉES (triées par drop rate):\n")
                print(f"{'#':<4} {'Drop%':<8} {'Relique(s)':<30} {'Mission':<25} {'Type':<15} {'Rotation':<10}")
                print("-" * 120)
                
                for idx, farm in enumerate(all_farms, 1):
                    # Formate l'affichage des reliques (peut être plusieurs)
                    relic_display = farm['relic'] if len(farm['relic']) < 30 else farm['relic'][:27] + '...'
                    print(f"{idx:<4} {farm['drop_rate']:<8.2f} {relic_display:<30} "
                          f"{farm['mission'][:24]:<25} {farm['type']:<15} {farm['rotation']:<10}")
                
                # Résumé des meilleures missions
                print("\n" + "=" * 80)
                print("⭐ TOP 5 MISSIONS RECOMMANDÉES")
                print("=" * 80 + "\n")
                
                for idx, farm in enumerate(all_farms[:5], 1):
                    print(f"{idx}. 🎯 {farm['mission']} ({farm['planet']})")
                    print(f"   Type: {farm['type']}")
                    print(f"   Rotation: {farm['rotation']}")
                    print(f"   Drop rate: {farm['drop_rate']}%")
                    
                    # Affiche les reliques (peut être plusieurs agrégées)
                    if isinstance(farm.get('relics'), list) and len(farm['relics']) > 1:
                        print(f"   Reliques: {', '.join(farm['relics'])} (cumulé)")
                    else:
                        print(f"   Relique: {farm['relic']}")
                    print()
            else:
                print("\n⚠️  Aucune mission de farm trouvée")
        
        print("\n" + "=" * 80)
        print("✅ ANALYSE TERMINÉE")
        print("=" * 80 + "\n")
    
    def analyze_complete_prime(self, item_name: str):
        """
        Analyse complète d'une warframe ou arme Prime avec tous ses composants
        """
        # Vérifie si c'est déjà un composant spécifique
        if "Blueprint" in item_name or "Chassis" in item_name or "Neuroptics" in item_name or \
           "Systems" in item_name or "Barrel" in item_name or "Receiver" in item_name or \
           "Stock" in item_name or "Blade" in item_name or "Handle" in item_name or \
           "Guard" in item_name or "Hilt" in item_name:
            # C'est déjà un composant spécifique, analyse normale
            self.analyze_prime_item(item_name)
            return
        
        # C'est le nom de base, cherche tous les composants
        components = self.get_prime_components(item_name)
        
        if not components:
            # Pas de composants trouvés, peut-être que c'est quand même un item valide
            self.analyze_prime_item(item_name)
            return
        
        print("=" * 80)
        print(f"🎯 ANALYSE COMPLÈTE DE: {item_name}")
        print("=" * 80)
        print(f"\n📦 {len(components)} composants détectés:\n")
        for comp in components:
            print(f"   • {comp}")
        print()
        
        # Analyse chaque composant
        all_farms_by_component = {}
        all_active_relics = {}
        
        for component in components:
            print("\n" + "─" * 80)
            print(f"📌 COMPOSANT: {component}")
            print("─" * 80 + "\n")
            
            relics = self.find_item_in_relics(component)
            
            if not relics:
                print(f"⚠️  Aucune relique trouvée pour {component}")
                continue
            
            # Filtre les reliques actives
            active_relics = []
            vaulted_relics = []
            
            for relic, data in relics.items():
                if self.is_relic_vaulted(data):
                    vaulted_relics.append(relic)
                else:
                    active_relics.append(relic)
            
            print(f"\n✅ Reliques ACTIVES: {len(active_relics)}")
            for relic in active_relics:
                print(f"   • {relic}")
            
            print(f"\n🔒 Reliques VAULTED: {len(vaulted_relics)}")
            for relic in vaulted_relics:
                print(f"   • {relic}")
            
            # Trouve les lieux de farm pour les reliques actives
            farms = []
            for relic in active_relics:
                relic_farms = self.find_relic_farm_locations(relic)
                for farm in relic_farms:
                    farm['relic'] = relic
                    farm['component'] = component
                    farms.append(farm)
            
            if farms:
                farms.sort(key=lambda x: x['drop_rate'], reverse=True)
                all_farms_by_component[component] = farms
                for relic in active_relics:
                    if relic not in all_active_relics:
                        all_active_relics[relic] = []
                    all_active_relics[relic].append(component)
                
                print(f"\n📋 Top 3 missions pour {component}:")
                for idx, farm in enumerate(farms[:3], 1):
                    print(f"   {idx}. {farm['mission']} ({farm['planet']}) - {farm['type']} Rot.{farm['rotation']} - {farm['drop_rate']}%")
        
        # Récapitulatif global
        if all_farms_by_component:
            print("\n" + "=" * 80)
            print("📊 RÉCAPITULATIF GLOBAL")
            print("=" * 80)
            
            # Trouve les missions communes
            mission_components = defaultdict(list)
            for component, farms in all_farms_by_component.items():
                for farm in farms:
                    mission_key = f"{farm['mission']} ({farm['planet']}) - {farm['type']} Rot.{farm['rotation']}"
                    mission_components[mission_key].append({
                        'component': component,
                        'drop_rate': farm['drop_rate'],
                        'relic': farm['relic']
                    })
            
            # Filtre les missions qui ont plusieurs composants
            common_missions = {k: v for k, v in mission_components.items() if len(v) > 1}
            
            if common_missions:
                print("\n⭐ MISSIONS MULTI-COMPOSANTS (farm plusieurs parties à la fois!):\n")
                for mission, comps in sorted(common_missions.items(), key=lambda x: len(x[1]), reverse=True):
                    print(f"🎯 {mission}")
                    print(f"   └─ {len(comps)} composants disponibles:")
                    for comp_info in comps:
                        comp_short = comp_info['component'].replace(item_name + " ", "")
                        print(f"      • {comp_short} via {comp_info['relic']} ({comp_info['drop_rate']}%)")
                    print()
            
            # Meilleure mission pour chaque composant
            print("\n🏆 MEILLEURES MISSIONS PAR COMPOSANT:\n")
            for component, farms in all_farms_by_component.items():
                if farms:
                    best = farms[0]
                    comp_short = component.replace(item_name + " ", "")
                    print(f"• {comp_short:30} → {best['mission']} ({best['planet']}) - {best['drop_rate']:.2f}%")
        
        print("\n" + "=" * 80)
        print("✅ ANALYSE COMPLÈTE TERMINÉE")
        print("=" * 80 + "\n")


def main():
    """Fonction principale"""
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║                 WARFRAME PRIME DROP ANALYZER                     ║
    ║          Analyse des drop rates officiels de Warframe            ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)


def cli_main():
    """Mode interactif CLI"""
    
    analyzer = WarframeDropAnalyzer()
    
    # Récupère les droptables
    if not analyzer.fetch_droptables():
        return
    
    # Mode interactif
    print("=" * 80)
    print("🎮 MODE INTERACTIF")
    print("=" * 80 + "\n")
    print("💡 Entrez le nom d'un item Prime OU d'un mod:")
    print("   • Pour un équipement complet: 'Gauss Prime', 'Acceltra Prime'")
    print("     (le script demandera le type: warframe/primary/melee/secondary)")
    print("   • Pour un composant spécifique: 'Gauss Prime Blueprint'")
    print("   • Pour un mod: 'Serration', 'Steel Fiber', 'Continuity'")
    print("💡 Tapez 'q', 'quit' ou 'exit' pour quitter\n")
    
    while True:
        try:
            item = input("🔎 Item/Mod à analyser: ").strip()
            
            if item.lower() in ['q', 'quit', 'exit', '']:
                print("\n👋 Au revoir, Tenno!")
                break
            
            if item:
                # Détecte si c'est un Prime item ou un mod
                if 'Prime' in item or 'Blueprint' in item:
                    analyzer.analyze_complete_prime(item)
                else:
                    # Assume que c'est un mod
                    analyzer.analyze_mod(item)
                print("\n")
        except KeyboardInterrupt:
            print("\n\n👋 Au revoir, Tenno!")
            break
        except EOFError:
            print("\n\n👋 Au revoir, Tenno!")
            break


def main():
    """Point d'entrée principal - mode CLI interactif"""
    cli_main()


if __name__ == "__main__":
    main()
