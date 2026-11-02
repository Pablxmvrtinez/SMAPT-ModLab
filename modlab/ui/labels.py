"""Textos en español para categorías y temáticas de ambos catálogos."""

CATEGORY_LABELS = {
    # CurseForge
    'Adventure and RPG': 'Aventura y RPG', 'World Gen': 'Generación del mundo', 'Cosmetic': 'Decoración',
    'Technology': 'Tecnología', 'Magic': 'Magia', 'Utility & QoL': 'Utilidad y comodidad', 'Food': 'Comida',
    'Farming': 'Agricultura', 'Mobs': 'Criaturas', 'Structures': 'Estructuras', 'Storage': 'Almacenamiento',
    'Biomes': 'Biomas', 'Dimensions': 'Dimensiones', 'Armor, Tools, and Weapons': 'Armas y equipo',
    'API and Library': 'Bibliotecas', 'Map and Information': 'Mapas e información', 'Performance': 'Rendimiento',
    'Server Utility': 'Servidores', 'Redstone': 'Redstone', 'Energy': 'Energía', 'Processing': 'Procesamiento',
    'Transport': 'Transporte', 'Ores and Resources': 'Minerales y recursos', 'Twitch Integration': 'Integraciones',
    'Education': 'Educación', 'Miscellaneous': 'Varios', 'Player Transport': 'Transporte de jugador',
    'Genetics': 'Genética', 'Automation': 'Automatización', 'Armor': 'Armaduras', 'Blood Magic': 'Magia de sangre',
    'Thermal Expansion': 'Thermal Expansion', 'Applied Energistics 2': 'Applied Energistics 2',
    'Addons': 'Complementos', 'Fluid': 'Fluidos', 'Fabric': 'Fabric', 'Create': 'Create', 'Bug Fixes': 'Correcciones',
    'Galacticraft': 'Galacticraft', 'Industrial Craft': 'IndustrialCraft', 'Tinker\'s Construct': 'Tinkers\' Construct',
    'Crafttweaker': 'CraftTweaker', 'KubeJS': 'KubeJS', 'Skyblock': 'Skyblock', 'QoL': 'Comodidad',
    # Modrinth
    'adventure': 'Aventura', 'cursed': 'Curiosos', 'decoration': 'Decoración', 'economy': 'Economía',
    'equipment': 'Equipo', 'food': 'Comida', 'game-mechanics': 'Mecánicas de juego', 'library': 'Bibliotecas',
    'magic': 'Magia', 'management': 'Gestión', 'minigame': 'Minijuegos', 'mobs': 'Criaturas',
    'optimization': 'Rendimiento', 'social': 'Social', 'storage': 'Almacenamiento', 'technology': 'Tecnología',
    'transportation': 'Transporte', 'utility': 'Utilidad', 'worldgen': 'Generación del mundo',
}

# (icono, etiqueta, categoría de CurseForge, categoría de Modrinth, búsqueda si no hay categoría)
THEMES = [
    ('sword', 'Aventura y RPG', 'Adventure and RPG', 'adventure', 'adventure'),
    ('wand', 'Magia', 'Magic', 'magic', 'magic'),
    ('gear', 'Tecnología', 'Technology', 'technology', 'technology'),
    ('cube', 'Construcción', 'Cosmetic', 'decoration', 'building'),
    ('leaf', 'Agricultura', 'Farming', None, 'farming'),
    ('ghost', 'Criaturas y jefes', 'Mobs', 'mobs', 'bosses'),
    ('castle', 'Estructuras', 'Structures', 'worldgen', 'structures'),
    ('mountain', 'Biomas', 'Biomes', 'worldgen', 'biomes'),
    ('portal', 'Dimensiones', 'Dimensions', None, 'dimension'),
    ('shield', 'Armas y equipo', 'Armor, Tools, and Weapons', 'equipment', 'weapons'),
    ('zap', 'Rendimiento', 'Performance', 'optimization', 'performance'),
    ('box', 'Almacenamiento', 'Storage', 'storage', 'storage'),
    ('heart', 'Comodidad', 'Utility & QoL', 'utility', 'quality of life'),
    ('map', 'Mapas', 'Map and Information', None, 'minimap'),
    ('utensils', 'Comida', 'Food', 'food', 'food'),
    ('circuit', 'Redstone', 'Redstone', None, 'redstone'),
    ('truck', 'Transporte', 'Transport', 'transportation', 'transport'),
    ('gem', 'Minerales', 'Ores and Resources', None, 'ores'),
    ('factory', 'Procesamiento', 'Processing', None, 'processing'),
    ('library', 'Bibliotecas', 'API and Library', 'library', 'library'),
    ('server', 'Servidores', 'Server Utility', None, 'server'),
    ('infinity', 'Todo el catálogo', None, None, ''),
]


def category_label(name):
    return CATEGORY_LABELS.get(name, name.replace('-', ' ').capitalize() if name and name.islower() else name)
