# services/tag_catalog.py
from __future__ import annotations

# Tags que aplican a cualquier categoría (útiles para MVP)
GLOBAL_TAGS: list[str] = [
    "Artesanal",
    "Hecho a mano",
    "Personalizado",
    "Regalos",
    "Para eventos",
    "Para empresas",
    "A domicilio",
    "Contra entrega",
    "Envíos",
    "WhatsApp",
    "Promociones",
]

TAGS_BY_CATEGORY: dict[str, list[str]] = {
    "Comida": [
        "Postres",
        "Galletas",
        "Brownies",
        "Tortas",
        "Panadería",
        "Repostería",
        "Snacks",
        "Refrigerios",
        "Saludable",
        "Sin azúcar",
        "Sin gluten",
        "Vegano",
        "Hecho en casa",
        "Para eventos",
        "Regalos",
        "Domicilio",
    ],
    "Bebidas": [
        "Café",
        "Café especial",
        "Chocolate",
        "Jugos",
        "Bebidas frías",
        "Bebidas calientes",
        "Kombucha",
        "Smoothies",
        "Para eventos",
        "Artesanal",
        "Domicilio",
    ],
    "Moda": [
        "Ropa",
        "Ropa deportiva",
        "Accesorios",
        "Bolsos",
        "Calzado",
        "Joyería",
        "Bisutería",
        "Personalizado",
        "Hecho a mano",
        "Regalos",
    ],
    "Belleza": [
        "Skincare",
        "Maquillaje",
        "Cabello",
        "Barbería",
        "Uñas",
        "Perfumería",
        "Jabones",
        "Cosmética natural",
        "Aromaterapia",
        "Regalos",
    ],
    "Hogar": [
        "Decoración",
        "Organización",
        "Cocina",
        "Limpieza",
        "Aromas",
        "Velas",
        "Plantas",
        "Textiles",
        "Personalizado",
        "Hecho a mano",
        "Regalos",
    ],
    "Servicios": [
        "Asesoría",
        "Diseño",
        "Eventos",
        "Fotografía",
        "Publicidad",
        "Impresiones",
        "Instalación",
        "Reparación",
        "Mantenimiento",
        "Domicilio",
        "Personalizado",
        "Urgente",
        "24/7",
        "Para empresas",
    ],
    "Tecnología": [
        "Impresión 3D",
        "Accesorios tech",
        "Soporte técnico",
        "Desarrollo web",
        "Automatización",
        "IA",
        "Apps",
        "Gadgets",
        "Personalizado",
    ],
    "Salud": [
        "Óptica",
        "Bienestar",
        "Terapias",
        "Nutrición",
        "Cuidado personal",
        "Fitness",
    ],
    "Educación": [
        "Clases",
        "Tutorías",
        "Cursos",
        "Talleres",
        "Idiomas",
        "Refuerzos",
    ],
    "Arte": [
        "Ilustración",
        "Pintura",
        "Artesanías",
        "Manualidades",
        "Personalizado",
        "Regalos",
        "Hecho a mano",
    ],
    "Mascotas": [
        "Snacks para mascotas",
        "Accesorios",
        "Higiene",
        "Entrenamiento",
        "Paseos",
        "Veterinaria",
        "IA para mascotas",
        "Bienestar animal",
    ],
}


def tags_for_category(category: str) -> list[str]:
    """
    Retorna lista de tags sugeridos para la categoría.
    Incluye tags globales al final (sin duplicados).
    """
    cat = (category or "").strip()
    base = TAGS_BY_CATEGORY.get(cat, [])
    # Unir base + global y dejar ordenado, sin duplicados
    merged = list(dict.fromkeys([*base, *GLOBAL_TAGS]))
    return merged

