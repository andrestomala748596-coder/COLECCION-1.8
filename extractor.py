import json
import os
import re
import unicodedata
from pathlib import Path

# ============================================================
# CATÁLOGO DE PELÍCULAS
# Este script NO extrae enlaces directos.
# Solo organiza los datos recibidos en peliculas/<CATEGORIA>.json
# y genera category_list.json.
# La extracción de enlaces se realizará dentro de Android Studio.
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "urls.txt"
MOVIES_DIR = BASE_DIR / "peliculas"
CATEGORY_LIST_FILE = BASE_DIR / "category_list.json"


def normalizar_categoria(categoria):
    """Devuelve un nombre de archivo seguro y consistente para la categoría."""
    categoria = str(categoria or "GENERAL").strip().upper()
    categoria = unicodedata.normalize("NFKD", categoria)
    categoria = "".join(c for c in categoria if not unicodedata.combining(c))
    categoria = re.sub(r"[^A-Z0-9 _-]", "", categoria)
    categoria = re.sub(r"[\s-]+", "_", categoria).strip("_")
    return categoria or "GENERAL"


def obtener_id(pelicula):
    """Busca un identificador estable para evitar duplicados en el catálogo."""
    return (
        pelicula.get("ID_VIDEO")
        or pelicula.get("ID_OKRU")
        or pelicula.get("TMDB_ID")
        or pelicula.get("ID")
    )


def cargar_json(ruta, valor_predeterminado):
    if not ruta.exists():
        return valor_predeterminado
    try:
        with ruta.open("r", encoding="utf-8") as archivo:
            return json.load(archivo)
    except (OSError, json.JSONDecodeError):
        print(f"⚠️ No se pudo leer {ruta.name}; se creará de nuevo.")
        return valor_predeterminado


def guardar_json(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    with temporal.open("w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, indent=2, ensure_ascii=False)
        archivo.write("\n")
    temporal.replace(ruta)


def limpiar_datos_para_catalogo(pelicula):
    """
    Conserva la información de origen y los enlaces de las plataformas.
    Elimina solamente los campos de enlaces directos generados por el
    extractor antiguo, ya que ahora esos enlaces se resolverán en Android.
    """
    pelicula = dict(pelicula)
    pelicula.pop("URLS_DIRECTAS", None)
    pelicula.pop("URL_DIRECTA", None)
    return pelicula


def fusionar_categoria_existente(ruta, peliculas_nuevas):
    existentes = cargar_json(ruta, [])
    if not isinstance(existentes, list):
        existentes = []

    posiciones = {}
    for indice, item in enumerate(existentes):
        if isinstance(item, dict):
            item_id = obtener_id(item)
            if item_id is not None:
                posiciones[str(item_id)] = indice

    for pelicula in peliculas_nuevas:
        pelicula_id = obtener_id(pelicula)
        clave = str(pelicula_id) if pelicula_id is not None else None

        if clave is not None and clave in posiciones:
            existentes[posiciones[clave]] = pelicula
        else:
            if clave is not None:
                posiciones[clave] = len(existentes)
            existentes.append(pelicula)

    return existentes


def main():
    print("📚 Iniciando organización del catálogo (sin extracción de vídeos)...")

    if not INPUT_FILE.exists():
        print("❌ No se encontró urls.txt.")
        return

    contenido = INPUT_FILE.read_text(encoding="utf-8").strip()
    if not contenido:
        print("ℹ️ urls.txt está vacío. No hay películas que organizar.")
        return

    try:
        peliculas = json.loads(contenido)
    except json.JSONDecodeError as error:
        print(f"❌ urls.txt no contiene JSON válido: {error}")
        return

    if not isinstance(peliculas, list):
        print("❌ El contenido de urls.txt debe ser una lista JSON de películas.")
        return

    MOVIES_DIR.mkdir(parents=True, exist_ok=True)
    agrupadas = {}

    for pelicula in peliculas:
        if not isinstance(pelicula, dict):
            continue

        pelicula = limpiar_datos_para_catalogo(pelicula)
        categoria_original = pelicula.get("CATEGORIA", "GENERAL")
        categoria = normalizar_categoria(categoria_original)
        pelicula["CATEGORIA"] = categoria
        agrupadas.setdefault(categoria, []).append(pelicula)

    # Crear o actualizar el JSON de cada categoría sin extraer enlaces.
    for categoria, peliculas_categoria in agrupadas.items():
        ruta = MOVIES_DIR / f"{categoria}.json"
        datos_actualizados = fusionar_categoria_existente(
            ruta, peliculas_categoria
        )
        guardar_json(ruta, datos_actualizados)
        print(f"✅ {ruta.relative_to(BASE_DIR)}: {len(datos_actualizados)} registros")

    # Mantener en la lista las categorías existentes que aún tengan archivo,
    # además de las categorías recibidas en esta ejecución.
    categorias_existentes = {
        ruta.stem
        for ruta in MOVIES_DIR.glob("*.json")
        if ruta.is_file() and ruta.name.lower() != "category_list.json"
    }
    categorias_finales = sorted(categorias_existentes | set(agrupadas.keys()))
    guardar_json(CATEGORY_LIST_FILE, categorias_finales)

    print(f"✅ Lista de categorías actualizada: {CATEGORY_LIST_FILE.name}")
    print("✅ Proceso terminado. No se realizó ninguna extracción de enlaces.")


if __name__ == "__main__":
    main()
