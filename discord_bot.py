#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Warframe Drop Analyzer - Discord Bot
Bot pour analyser les drops Prime et mods sur Discord
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
from typing import Optional
import traceback

# Import de l'analyseur
from warframe_drop_analyzer import WarframeDropAnalyzer

# Configuration
TOKEN = os.getenv('DISCORD_BOT_TOKEN')  # À définir dans les variables d'environnement
INTENTS = discord.Intents.default()
INTENTS.message_content = True

bot = commands.Bot(command_prefix='!', intents=INTENTS)

# Instance globale de l'analyseur
analyzer = None


@bot.event
async def on_ready():
    """Initialisation du bot"""
    global analyzer
    print(f'✅ Bot connecté en tant que {bot.user}')
    print(f'📊 Serveurs: {len(bot.guilds)}')
    
    # Charge les droptables au démarrage
    print('📥 Chargement des droptables Warframe...')
    analyzer = WarframeDropAnalyzer()
    if analyzer.fetch_droptables():
        print('✅ Droptables chargées!')
    else:
        print('❌ Erreur de chargement des droptables')
    
    # Synchronise les slash commands
    try:
        synced = await bot.tree.sync()
        print(f'✅ {len(synced)} commandes synchronisées')
    except Exception as e:
        print(f'❌ Erreur de synchronisation: {e}')


@bot.tree.command(name="prime", description="Analyse un item Prime (warframe ou arme)")
@app_commands.describe(
    item="Nom de l'item Prime (ex: Gauss Prime, Acceltra Prime)",
    type="Type d'équipement",
    filters="Filtres à appliquer (ex: 'Spy, Duviri')"
)
@app_commands.choices(type=[
    app_commands.Choice(name="Warframe", value="warframe"),
    app_commands.Choice(name="Arme Primary", value="primary"),
    app_commands.Choice(name="Arme Melee", value="melee"),
    app_commands.Choice(name="Arme Secondary", value="secondary"),
])
async def prime_command(
    interaction: discord.Interaction,
    item: str,
    type: Optional[app_commands.Choice[str]] = None,
    filters: Optional[str] = None
):
    """Commande /prime pour analyser un item Prime"""
    await interaction.response.defer(thinking=True)
    
    try:
        if not analyzer or not analyzer.soup:
            await interaction.followup.send("❌ Bot non initialisé. Réessayez dans quelques secondes.")
            return
        
        # Parse les filtres
        filter_list = []
        if filters:
            filter_list = [f.strip() for f in filters.split(',')]
        
        # Détermine si c'est un composant spécifique ou un item complet
        is_specific = any(keyword in item for keyword in [
            'Blueprint', 'Chassis', 'Neuroptics', 'Systems',
            'Barrel', 'Receiver', 'Stock', 'Blade', 'Handle', 'Guard', 'Hilt'
        ])
        
        if is_specific or not type:
            # Analyse directe d'un composant
            result = await analyze_single_component(item, filter_list)
        else:
            # Analyse complète avec type
            result = await analyze_complete_prime(item, type.value, filter_list)
        
        # Envoie les résultats (Discord limite à 2000 caractères par message)
        await send_long_message(interaction, result)
        
    except Exception as e:
        error_msg = f"❌ Erreur: {str(e)}\n```{traceback.format_exc()[:500]}```"
        await interaction.followup.send(error_msg)


@bot.tree.command(name="mod", description="Analyse un mod Warframe")
@app_commands.describe(
    mod="Nom du mod (ex: Serration, Steel Fiber)",
    filters="Filtres à appliquer (ex: 'Spy, Duviri')"
)
async def mod_command(
    interaction: discord.Interaction,
    mod: str,
    filters: Optional[str] = None
):
    """Commande /mod pour analyser un mod"""
    await interaction.response.defer(thinking=True)
    
    try:
        if not analyzer or not analyzer.soup:
            await interaction.followup.send("❌ Bot non initialisé. Réessayez dans quelques secondes.")
            return
        
        # Parse les filtres
        filter_list = []
        if filters:
            filter_list = [f.strip() for f in filters.split(',')]
        
        # Trouve les missions
        all_missions = analyzer.find_mod_in_missions(mod)
        
        if not all_missions:
            await interaction.followup.send(f"⚠️ Mod '{mod}' non trouvé dans les droptables.")
            return
        
        # Applique les filtres
        missions = analyzer.apply_mission_filters(all_missions, filter_list)
        
        if not missions:
            await interaction.followup.send("⚠️ Toutes les missions ont été exclues par les filtres.")
            return
        
        # Trie par drop rate
        missions.sort(key=lambda x: x['drop_rate'], reverse=True)
        
        # Construit le message
        result = f"# 🔧 {mod}\n\n"
        result += f"**{len(missions)} missions trouvées**\n\n"
        
        # Top 10
        result += "## ⭐ Top 10 Missions\n"
        for idx, farm in enumerate(missions[:10], 1):
            result += f"**{idx}.** {farm['mission']} ({farm['planet']})\n"
            result += f"   • Type: {farm['type']}\n"
            result += f"   • Rotation: {farm['rotation']}\n"
            result += f"   • Drop: **{farm['drop_rate']:.2f}%** ({farm['rarity']})\n\n"
        
        await send_long_message(interaction, result)
        
    except Exception as e:
        error_msg = f"❌ Erreur: {str(e)}\n```{traceback.format_exc()[:500]}```"
        await interaction.followup.send(error_msg)


@bot.tree.command(name="reload", description="Recharge les droptables Warframe (admin uniquement)")
async def reload_command(interaction: discord.Interaction):
    """Commande /reload pour recharger les données"""
    # Vérifie les permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Commande réservée aux administrateurs.", ephemeral=True)
        return
    
    await interaction.response.defer(thinking=True)
    
    try:
        global analyzer
        print('📥 Rechargement des droptables...')
        analyzer = WarframeDropAnalyzer()
        
        if analyzer.fetch_droptables():
            await interaction.followup.send("✅ Droptables rechargées avec succès!")
        else:
            await interaction.followup.send("❌ Erreur lors du rechargement des droptables.")
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur: {str(e)}")


@bot.tree.command(name="help", description="Affiche l'aide du bot")
async def help_command(interaction: discord.Interaction):
    """Commande /help"""
    help_text = """
# 🤖 Warframe Drop Analyzer Bot

## Commandes disponibles:

### `/prime <item> [type] [filters]`
Analyse un item Prime complet ou un composant spécifique.

**Exemples:**
• `/prime item:Gauss Prime type:Warframe`
• `/prime item:Acceltra Prime type:Primary filters:Spy,Duviri`
• `/prime item:Gauss Prime Blueprint` (composant spécifique)

**Types disponibles:**
• `Warframe` - Warframes Prime
• `Primary` - Armes primaires
• `Melee` - Armes de mêlée
• `Secondary` - Armes secondaires

### `/mod <mod> [filters]`
Analyse un mod et trouve les meilleures missions pour le farmer.

**Exemples:**
• `/mod mod:Serration`
• `/mod mod:Steel Fiber filters:Defense,Spy`

### `/reload`
Recharge les droptables (admin uniquement)

### `/help`
Affiche ce message d'aide

## Filtres
Vous pouvez exclure certains types de missions en utilisant le paramètre `filters`.
Séparez les filtres par des virgules.

**Exemples de filtres:**
• `Spy` - Exclut les missions d'espionnage
• `Duviri` - Exclut les missions Duviri
• `Defense,Spy,Event` - Exclut plusieurs types

## Notes
• Le bot agrège automatiquement les drops de plusieurs reliques
• Les résultats sont triés par taux de drop décroissant
• Les missions multi-composants sont mises en avant
    """
    await interaction.response.send_message(help_text, ephemeral=True)


# Fonctions helper

async def analyze_single_component(item_name: str, filters: list) -> str:
    """Analyse un composant Prime unique"""
    # Trouve les reliques
    relics = analyzer.find_item_in_relics(item_name)
    
    if not relics:
        return f"⚠️ '{item_name}' non trouvé dans les reliques."
    
    # Sépare actives/vaulted
    active_relics = []
    vaulted_relics = []
    
    for relic, data in relics.items():
        if analyzer.is_relic_vaulted(data):
            vaulted_relics.append(relic)
        else:
            active_relics.append(relic)
    
    result = f"# 🎯 {item_name}\n\n"
    result += f"**Reliques actives:** {len(active_relics)}\n"
    result += f"**Reliques vaulted:** {len(vaulted_relics)}\n\n"
    
    if not active_relics:
        result += "⚠️ Toutes les reliques sont vaulted.\n"
        return result
    
    # Collecte les missions
    all_farms = []
    for relic in active_relics:
        farms = analyzer.find_relic_farm_locations(relic)
        for farm in farms:
            farm['relic'] = relic
            all_farms.append(farm)
    
    # Applique filtres et agrège
    if filters:
        all_farms = analyzer.apply_mission_filters(all_farms, filters)
    
    all_farms = analyzer.aggregate_mission_drops(all_farms)
    all_farms.sort(key=lambda x: x['drop_rate'], reverse=True)
    
    # Top 10
    result += "## ⭐ Top 10 Missions\n\n"
    for idx, farm in enumerate(all_farms[:10], 1):
        relics_str = farm['relic'] if isinstance(farm['relic'], str) else ', '.join(farm['relics'])
        result += f"**{idx}.** {farm['mission']} ({farm['planet']})\n"
        result += f"   • Type: {farm['type']} - {farm['rotation']}\n"
        result += f"   • Drop: **{farm['drop_rate']:.2f}%**\n"
        if len(farm.get('relics', [])) > 1:
            result += f"   • Reliques: {relics_str} (cumulé)\n"
        else:
            result += f"   • Relique: {relics_str}\n"
        result += "\n"
    
    return result


async def analyze_complete_prime(base_name: str, equipment_type: str, filters: list) -> str:
    """Analyse tous les composants d'un item Prime"""
    # Détermine les patterns selon le type
    type_patterns = {
        'warframe': ['Blueprint', 'Chassis Blueprint', 'Neuroptics Blueprint', 'Systems Blueprint'],
        'primary': ['Blueprint', 'Stock', 'Barrel', 'Receiver'],
        'melee': ['Blueprint', 'Blade', 'Handle', 'Guard'],  # Simplifié
        'secondary': ['Blueprint', 'Barrel', 'Receiver']
    }
    
    parts = type_patterns.get(equipment_type, [])
    
    # Cherche les composants
    valid_parts = []
    for part in parts:
        component_name = f"{base_name} {part}"
        relics = analyzer.find_item_in_relics(component_name)
        if relics:
            valid_parts.append(component_name)
    
    if not valid_parts:
        return f"⚠️ Aucun composant trouvé pour {base_name} (type: {equipment_type})"
    
    result = f"# 🎯 {base_name}\n\n"
    result += f"**{len(valid_parts)} composants détectés**\n\n"
    
    # Analyse chaque composant
    all_mission_components = {}
    
    for component in valid_parts:
        comp_short = component.replace(f"{base_name} ", "")
        result += f"## 📦 {comp_short}\n\n"
        
        # Analyse simplifié
        relics = analyzer.find_item_in_relics(component)
        active_relics = [r for r, d in relics.items() if not analyzer.is_relic_vaulted(d)]
        
        if not active_relics:
            result += "⚠️ Toutes les reliques sont vaulted\n\n"
            continue
        
        # Top 3 missions pour ce composant
        all_farms = []
        for relic in active_relics[:2]:  # Limite à 2 reliques par composant
            farms = analyzer.find_relic_farm_locations(relic)
            for farm in farms[:50]:  # Limite à 50 missions par relique
                farm['relic'] = relic
                all_farms.append(farm)
                # Track pour missions communes
                mission_key = f"{farm['mission']}|{farm['planet']}|{farm['rotation']}"
                if mission_key not in all_mission_components:
                    all_mission_components[mission_key] = []
                all_mission_components[mission_key].append(comp_short)
        
        if filters:
            all_farms = analyzer.apply_mission_filters(all_farms, filters)
        
        all_farms = analyzer.aggregate_mission_drops(all_farms)
        all_farms.sort(key=lambda x: x['drop_rate'], reverse=True)
        
        for idx, farm in enumerate(all_farms[:3], 1):
            result += f"**{idx}.** {farm['mission']} ({farm['planet']}) - {farm['rotation']}\n"
            result += f"      Drop: **{farm['drop_rate']:.2f}%**\n"
        result += "\n"
    
    # Missions multi-composants
    common = {k: v for k, v in all_mission_components.items() if len(v) > 1}
    if common:
        result += "## 🎁 Missions Multi-Composants\n\n"
        for mission_key, comps in sorted(common.items(), key=lambda x: len(x[1]), reverse=True)[:5]:
            parts = mission_key.split('|')
            result += f"**{parts[0]} ({parts[1]}) - {parts[2]}**\n"
            result += f"   • {len(comps)} composants: {', '.join(comps)}\n\n"
    
    return result


async def send_long_message(interaction: discord.Interaction, content: str):
    """Envoie un message long en le découpant si nécessaire"""
    max_length = 1900  # Limite Discord ~2000, on garde une marge
    
    if len(content) <= max_length:
        await interaction.followup.send(content)
        return
    
    # Découpe en plusieurs messages
    parts = []
    current = ""
    
    for line in content.split('\n'):
        if len(current) + len(line) + 1 > max_length:
            parts.append(current)
            current = line + '\n'
        else:
            current += line + '\n'
    
    if current:
        parts.append(current)
    
    # Envoie les parties
    for i, part in enumerate(parts):
        if i == 0:
            await interaction.followup.send(part)
        else:
            await interaction.channel.send(part)
        await asyncio.sleep(0.5)  # Évite le rate limit


def main():
    """Lance le bot"""
    if not TOKEN:
        print("❌ ERREUR: Variable d'environnement DISCORD_BOT_TOKEN non définie")
        print("Définissez-la avec: set DISCORD_BOT_TOKEN=votre_token")
        return
    
    print("🚀 Démarrage du bot Warframe Drop Analyzer...")
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
