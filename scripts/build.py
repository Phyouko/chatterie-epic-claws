#!/usr/bin/env python3
"""Build du site Chatterie Epic Claws (exécuté par Netlify à chaque déploiement).

1. Copie le site tel quel dans dist/.
2. Optimise les images référencées par le CMS (HEIC iPhone, PNG trop lourds...).
3. Écrit les fiches directement dans les pages (chatons, reproductrices, reproducteurs, articles)
   pour qu'elles soient lisibles sans JavaScript, et génère une vraie page par article
   (/articles/<slug>/), par chaton (/chatons/<slug>/) et par parent (/reproducteurs/<slug>/,
   /reproductrices/<slug>/), plus la galerie des chatons adoptés (/chatons-adoptes/).
4. Complète les mentions légales, le pied de page (SIREN) et le bandeau « prochaine portée »
   à partir des réglages saisis dans l'admin.
5. Génère sitemap.xml.

Chaque étape est isolée : si l'une échoue, le site reste publiable (liens d'origine conservés).
Les gabarits HTML ci-dessous doivent rester alignés sur ceux de js/chatons.js et js/cats.js,
qui ne servent plus que de secours quand ce script n'a pas tourné.
Compatible Python 3.8+.
"""
import datetime
import html
import json
import re
import shutil
import traceback
import unicodedata
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
SITE = "https://chatterieepicclaws.fr"
SITE_NAME = "Chatterie Epic Claws"
SHORT_NAME = "Epic Claws"
DEFAULT_OG_IMAGE = "/images/hero.jpg"
OPT_DIR = "images/optimized"
WHATSAPP = "33685499971"

EXCLUDE_TOP = {
    ".git", ".github", ".claude", "dist", "scripts", "node_modules", "__pycache__",
    "requirements.txt", "requirements-images.txt", "netlify.toml", ".gitignore",
    "netlify", "package.json", "package-lock.json",
}

PAW_SVG = (
    '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="6" cy="9" r="2"/><circle cx="10.5" cy="6.2" r="2"/>'
    '<circle cx="15.5" cy="6.2" r="2"/><circle cx="19" cy="9" r="2"/><path d="M12.5 11c3 0 5.5 2.2 5.5 4.6 0 '
    '1.9-1.6 3.4-3.6 3.4-1 0-1.6-.4-2.4-.4s-1.4.4-2.4.4c-2 0-3.6-1.5-3.6-3.4C6.5 13.2 9 11 12.5 11Z"/></svg>'
)


def esc(value):
    return html.escape(str(value), quote=True)


def slugify(value):
    text = unicodedata.normalize("NFKD", str(value).lower().replace("œ", "oe").replace("æ", "ae"))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def read_json_optional(path):
    try:
        data = read_json(path)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def step(name, func, *args):
    try:
        return func(*args)
    except Exception:
        print("[ERREUR] étape '%s' ignorée :" % name)
        traceback.print_exc()
        return None


def text_of(value):
    return str(value).strip() if value not in (None, "") else ""


def truncate(text, limit=158):
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:.-")
    return cut + "…"


def plain_text(markdown_html):
    return html.unescape(re.sub(r"<[^>]+>", " ", markdown_html))


def abs_url(path):
    if re.match(r"^https?://", path):
        return path
    return SITE + "/" + quote(path.lstrip("/"), safe="/%")


def seo_title(base):
    """Ajoute le nom du site tant que le titre reste entier dans Google (60 caractères environ)."""
    full = "%s | %s" % (base, SHORT_NAME)
    return full if len(full) <= 60 else base


def de_nom(nom):
    first = slugify(nom)[:1]
    return ("d'" if first in "aeiouyh" else "de ") + nom


def unique_slug(base, used):
    slug, n = base, 2
    while slug in used:
        slug, n = "%s-%d" % (base, n), n + 1
    used.add(slug)
    return slug


# --------------------------------------------------------------------------- copie

def copy_site():
    if DIST.exists():
        shutil.rmtree(DIST)

    def ignore(directory, names):
        if Path(directory) == ROOT:
            return [n for n in names if n in EXCLUDE_TOP]
        return [n for n in names if n == "__pycache__"]

    shutil.copytree(ROOT, DIST, ignore=ignore)


# --------------------------------------------------------------------------- images

def load_image_libs():
    try:
        from PIL import Image, ImageOps  # noqa: F401
    except Exception:
        print("[images] Pillow indisponible : optimisation ignorée")
        return None
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except Exception:
        print("[images] pillow-heif indisponible : les photos HEIC ne seront pas converties")
    return Image, ImageOps


def make_optimizer():
    libs = load_image_libs()
    cache = {}
    stats = {"converted": 0}

    def optimize(ref, max_side=1100):
        if libs is None or not isinstance(ref, str) or not ref.strip():
            return ref
        if re.match(r"^(https?:)?//", ref):
            return ref
        key = (ref, max_side)
        if key in cache:
            return cache[key]
        Image, ImageOps = libs
        result = ref
        try:
            rel = ref.lstrip("/")
            src = DIST / rel
            ext = src.suffix.lower()
            if src.is_file() and ext in (".heic", ".heif", ".jpg", ".jpeg", ".png", ".webp"):
                size = src.stat().st_size
                is_heic = ext in (".heic", ".heif")
                with Image.open(src) as probe:
                    width, height = probe.size
                if is_heic or max(width, height) > max_side * 1.15 or size > 250 * 1024:
                    out_rel = "%s/%s.jpg" % (OPT_DIR, slugify(rel.rsplit(".", 1)[0]))
                    out = DIST / out_rel
                    if not out.exists():
                        out.parent.mkdir(parents=True, exist_ok=True)
                        with Image.open(src) as im:
                            im = ImageOps.exif_transpose(im)
                            if im.mode in ("RGBA", "LA", "P"):
                                rgba = im.convert("RGBA")
                                background = Image.new("RGB", rgba.size, (255, 255, 255))
                                background.paste(rgba, mask=rgba.split()[-1])
                                im = background
                            im = im.convert("RGB")
                            scale = min(1.0, float(max_side) / max(im.size))
                            if scale < 1.0:
                                im = im.resize(
                                    (max(1, round(im.width * scale)), max(1, round(im.height * scale))),
                                    Image.LANCZOS,
                                )
                            im.save(out, "JPEG", quality=82, optimize=True, progressive=True)
                    if is_heic or out.stat().st_size < size:
                        result = ("/" if ref.startswith("/") else "") + out_rel
                        stats["converted"] += 1
                        print("[images] %s -> %s (%d Ko -> %d Ko)" % (ref, out_rel, size // 1024, out.stat().st_size // 1024))
        except Exception as exc:
            print("[images] %s ignoré : %s" % (ref, exc))
        cache[key] = result
        return result

    return optimize


MD_IMAGE = re.compile(r"(!\[[^\]]*\]\()([^)\s]+)([^)]*\))")


def optimize_extras(item, optimize):
    extras = item.get("photos_supplementaires")
    if extras:
        item["photos_supplementaires"] = [
            optimize(p) if isinstance(p, str)
            else (dict(p, image=optimize(p["image"])) if isinstance(p, dict) and p.get("image") else p)
            for p in extras
        ]


def optimize_data(data, optimize):
    for chaton in data["chatons"].get("chatons", []):
        if chaton.get("photo"):
            chaton["photo"] = optimize(chaton["photo"])
        optimize_extras(chaton, optimize)
    for key in ("reproductrices", "reproducteurs"):
        for cat in data[key].get(key, []):
            if cat.get("photo"):
                cat["photo"] = optimize(cat["photo"])
            optimize_extras(cat, optimize)
    for article in data["articles"].get("articles", []):
        if article.get("image"):
            article["image"] = optimize(article["image"], 1600)
        if article.get("corps"):
            article["corps"] = MD_IMAGE.sub(
                lambda m: m.group(1) + optimize(m.group(2), 1400) + m.group(3), article["corps"]
            )


# --------------------------------------------------------------------------- outils de page

def make_markdown():
    from markdown_it import MarkdownIt
    return MarkdownIt("commonmark", {"html": True, "linkify": False}).enable("table").enable("strikethrough")


def head_block(title, desc, path, image=None, og_type="website", jsonld=None, og_title=None):
    canonical = SITE + path
    social_title = og_title or title
    lines = [
        '<link rel="canonical" href="%s">' % esc(canonical),
        '<meta name="robots" content="index, follow, max-image-preview:large">',
        '<meta property="og:locale" content="fr_FR">',
        '<meta property="og:site_name" content="%s">' % esc(SITE_NAME),
        '<meta property="og:type" content="%s">' % og_type,
        '<meta property="og:title" content="%s">' % esc(social_title),
        '<meta property="og:description" content="%s">' % esc(desc),
        '<meta property="og:url" content="%s">' % esc(canonical),
        '<meta name="twitter:card" content="summary_large_image">',
        '<meta name="twitter:title" content="%s">' % esc(social_title),
        '<meta name="twitter:description" content="%s">' % esc(desc),
    ]
    if image:
        lines.append('<meta property="og:image" content="%s">' % esc(image))
        lines.append('<meta name="twitter:image" content="%s">' % esc(image))
    for block in jsonld or []:
        payload = json.dumps(block, ensure_ascii=False).replace("</", "<\\/")
        lines.append('<script type="application/ld+json">%s</script>' % payload)
    return "\n".join(lines)


def apply_head(template, title, desc, head_extra):
    out = template.replace("<head>", '<head>\n<base href="/">', 1)
    out = re.sub(r"<title>.*?</title>", lambda m: "<title>%s</title>" % esc(title), out, count=1, flags=re.S)
    out = re.sub(
        r'<meta name="description" content="[^"]*">',
        lambda m: '<meta name="description" content="%s">' % esc(desc),
        out, count=1,
    )
    out = re.sub(r'<meta name="robots" content="noindex">\s*', "", out, count=1)
    out = out.replace("</head>", head_extra + "\n</head>", 1)
    return out


def breadcrumb(items):
    return {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": SITE + path}
            for i, (name, path) in enumerate(items)
        ],
    }


def set_active_nav(page, href):
    def fix(match):
        nav = match.group(0).replace(' class="active"', "")
        return nav.replace('<a href="%s"' % href, '<a href="%s" class="active"' % href, 1) if href else nav
    return re.sub(r'<nav class="nav-links">.*?</nav>', fix, page, count=1, flags=re.S)


def shell_page(template, main_html, active_href=None):
    """Page générée à partir de la coque chaton.html (en-tête, pied de page, icônes)."""
    page = re.sub(r'<main id="fiche-chaton">.*?</main>', lambda m: main_html, template, count=1, flags=re.S)
    page = page.replace('<script src="js/chatons.js"></script>\n', "")
    return set_active_nav(page, active_href)


def fill_grid(page, element_id, inner_html):
    """Écrit les fiches dans la grille et la marque comme déjà rendue (le JS ne la refait pas)."""
    pattern = r'<div([^>]*)\bid="%s"([^>]*)>\s*(?:<p>[^<]*</p>)?\s*</div>' % re.escape(element_id)
    return re.subn(
        pattern,
        lambda m: '<div%sid="%s"%s data-prerendered="true">%s</div>' % (m.group(1), element_id, m.group(2), inner_html),
        page, count=1,
    )


MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
          "septembre", "octobre", "novembre", "décembre"]


def format_date(date_str):
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", date_str or "")
    if not match:
        return date_str or ""
    year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
    return "%d %s %d" % (day, MONTHS[month - 1], year)


def parse_fr_date(value):
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", str(value or "").strip())
    if not match:
        return None
    try:
        return datetime.date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
    except ValueError:
        return None


def photo_list(item):
    extras = [p if isinstance(p, str) else (p or {}).get("image") for p in (item.get("photos_supplementaires") or [])]
    return [p for p in [item.get("photo")] + extras if p]


def gallery_html(photos, alt, badges=""):
    main = '<img src="%s" alt="%s" fetchpriority="high">' % (esc(photos[0]), esc(alt)) if photos else ""
    thumbs = ""
    if len(photos) > 1:
        thumbs = '<div class="fiche-gallery-thumbs">%s</div>' % "".join(
            '<button type="button" class="fiche-thumb%s" data-src="%s"><img src="%s" alt="%s, photo %d" loading="lazy"></button>'
            % (" active" if i == 0 else "", esc(p), esc(p), esc(alt.split(",")[0]), i + 1)
            for i, p in enumerate(photos)
        )
    return '<div class="fiche-gallery"><div class="fiche-gallery-main">%s%s</div>%s</div>' % (badges, main, thumbs)


def quick_fact(icon, label, value, full=False):
    return (
        '<div class="quick-fact%s"><span class="qf-icon"><i class="fa-solid %s"></i></span>'
        '<span><span class="qf-label">%s</span><span class="qf-value">%s</span></span></div>'
        % (" full" if full else "", icon, esc(label), value)
    )


# --------------------------------------------------------------------------- adresses

def is_visible(item):
    return item.get("visible") is not False


def status_slug(chaton):
    return slugify(chaton.get("statut") or "Disponible")


def is_adopted(chaton):
    return status_slug(chaton) in ("adopte", "adoptee")


def is_reserved(chaton):
    return status_slug(chaton) in ("reserve", "reservee")


def status_class(chaton, base="kitten-status"):
    if is_adopted(chaton):
        return base + " adopted"
    return base + " reserved" if is_reserved(chaton) else base


def assign_urls(data):
    """Donne son adresse à chaque fiche avant de générer quoi que ce soit (les pages se citent entre elles)."""
    for key in ("reproductrices", "reproducteurs"):
        used = set()
        for cat in data[key].get(key, []):
            base = slugify(cat.get("nom") or "")
            if base and is_visible(cat):
                cat["url"] = "/%s/%s/" % (key, unique_slug(base, used))
    used = set()
    for chaton in data["chatons"].get("chatons", []):
        base = slugify(chaton.get("nom") or "")
        if base and is_visible(chaton):
            chaton["url"] = "/chatons/%s/" % unique_slug(base, used)
    used = set()
    for article in data["articles"].get("articles", []):
        base = slugify(article.get("slug") or article.get("titre") or "")
        if base and article.get("titre") and is_visible(article):
            article["url"] = "/articles/%s/" % unique_slug(base, used)


def parent_index(data):
    index = {}
    for cat in data["reproductrices"].get("reproductrices", []):
        if cat.get("nom"):
            index[cat["nom"]] = (cat, False)
    for cat in data["reproducteurs"].get("reproducteurs", []):
        if cat.get("nom"):
            index[cat["nom"]] = (cat, True)
    return index


# --------------------------------------------------------------------------- articles

def article_card(article, url):
    bg = article.get("image") or "images/logo.avif"
    date = article.get("date", "")
    return (
        '<a class="teaser-card article-card" style="background-image:url(\'%s\')" href="%s">'
        '<div class="teaser-body"><span class="article-date">%s</span><h3>%s</h3><p>%s</p>'
        '<span class="teaser-link">Lire la suite →</span></div></a>'
        % (esc(bg), esc(url), esc(format_date(date)), esc(article.get("titre", "")), esc(article.get("extrait", "")))
    )


def published_articles(data):
    return [a for a in data["articles"].get("articles", []) if a.get("url")]


def build_articles(data, md):
    pages = published_articles(data)
    template = (DIST / "article.html").read_text(encoding="utf-8")
    template = template.replace(
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js"></script>\n', ""
    )
    has_waitlist = (DIST / "liste-attente.html").exists()
    for article in pages:
        url = article["url"]
        body = md.render(article.get("corps", ""))
        body = body.replace("<img ", '<img loading="lazy" decoding="async" ')
        title_text = article["titre"]
        desc_source = text_of(article.get("description_seo")) or article.get("extrait") or plain_text(body)
        desc = truncate(re.sub(r"(\.\.\.|…)\s*$", "", desc_source).strip() or plain_text(body))
        image = abs_url(article["image"]) if article.get("image") else abs_url(DEFAULT_OG_IMAGE)
        cover = (
            '<img class="article-cover" src="%s" alt="%s" fetchpriority="high">'
            % (esc(article["image"]), esc(title_text))
            if article.get("image") else ""
        )
        content = (
            '<div id="article-content" data-prerendered="true">'
            '<div class="article-header"><span class="article-date">%s</span><h1>%s</h1></div>'
            '%s<div class="article-body">%s</div></div>'
            % (esc(format_date(article.get("date", ""))), esc(title_text), cover, body)
        )
        page = re.sub(
            r'<div id="article-content">\s*<p>[^<]*</p>\s*</div>',
            lambda m: content, template, count=1,
        )
        jsonld = [
            {
                "@context": "https://schema.org", "@type": "Article",
                "headline": title_text[:110], "description": desc, "image": [image],
                "datePublished": article.get("date"), "dateModified": article.get("date"),
                "inLanguage": "fr-FR",
                "author": {"@type": "Organization", "name": SITE_NAME, "url": SITE + "/"},
                "publisher": {"@type": "Organization", "name": SITE_NAME,
                              "logo": {"@type": "ImageObject", "url": SITE + "/images/icon-192.png"}},
                "mainEntityOfPage": {"@type": "WebPage", "@id": SITE + url},
            },
            breadcrumb([("Accueil", "/"), ("Nos Articles", "/articles.html"), (title_text, url)]),
        ]
        # Titre de l'onglet et de Google : version courte si elle existe, sinon le titre de l'article.
        page_title = seo_title(text_of(article.get("titre_seo")) or title_text)
        page = apply_head(page, page_title, desc, head_block(page_title, desc, url, image, "article", jsonld, og_title=title_text))

        others = [a for a in pages if a is not article]
        others.sort(key=lambda a: a.get("date", ""), reverse=True)
        related = "".join(article_card(a, a["url"]) for a in others[:2])
        waitlist_btn = (
            '<a href="liste-attente.html" class="btn btn-outline">Rejoindre la liste d\'attente</a>' if has_waitlist
            else '<a href="contact.html" class="btn btn-outline">Nous contacter</a>'
        )
        extra = (
            '<section class="section section-alt article-cta"><div class="container">'
            '<h2>Vous cherchez un chaton Maine Coon ?</h2>'
            '<p>Nos chatons grandissent en famille à Le Soler, près de Perpignan : identifiés, vaccinés, '
            'vermifugés et accompagnés de leur pedigree.</p>'
            '<div class="article-cta-actions"><a href="chatons.html" class="btn btn-primary">Voir les chatons disponibles</a>'
            '%s</div></div></section>' % waitlist_btn
        )
        if related:
            extra += (
                '<section class="section section-light"><div class="container">'
                '<div class="section-head"><span class="kicker">À lire aussi</span><h2>Continuer la lecture</h2></div>'
                '<div class="grid grid-2">%s</div></div></section>' % related
            )
        page = page.replace('<footer class="site-footer">', extra + '\n<footer class="site-footer">', 1)

        out_dir = DIST / url.strip("/")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(page, encoding="utf-8")
    print("[articles] %d page(s) générée(s)" % len(pages))
    return [(a["url"], a.get("date")) for a in pages]


def build_article_list(data):
    path = DIST / "articles.html"
    pages = sorted(published_articles(data), key=lambda a: a.get("date", ""), reverse=True)
    if not pages:
        return
    page, count = fill_grid(path.read_text(encoding="utf-8"), "articles-grid",
                            "".join(article_card(a, a["url"]) for a in pages))
    if count:
        path.write_text(page, encoding="utf-8")


# --------------------------------------------------------------------------- reproducteurs / reproductrices

def cat_alt(nom, is_male):
    return "%s, %s Maine Coon" % (nom, "mâle reproducteur" if is_male else "chatte reproductrice")


def render_cat_card(cat, is_male, index=0):
    nom = cat.get("nom") or ""
    url = cat.get("url")
    price = '<span class="cat-price">Saillie — %s&nbsp;€</span>' % esc(cat["prix_saillie"]) if cat.get("prix_saillie") else ""
    titre = '<div><dt>Titre</dt><dd>%s</dd></div>' % esc(cat["titre"]) if cat.get("titre") else ""
    name = '<a href="%s">%s</a>' % (esc(url), esc(nom)) if url else esc(nom)
    photo = '<img src="%s" alt="%s"%s>' % (esc(cat.get("photo") or ""), esc(cat_alt(nom, is_male)), ' loading="lazy"' if index else "")
    if url:
        photo = '<a href="%s" aria-label="Voir la fiche %s">%s</a>' % (esc(url), esc(de_nom(nom)), photo)
    actions = []
    if url:
        actions.append('<a href="%s" class="btn btn-outline">Voir sa fiche complète</a>' % esc(url))
    if is_male:
        actions.append(
            '<a href="contact.html?sujet=saillie&nom=%s" class="btn btn-primary">Demander une saillie avec %s</a>'
            % (quote(nom, safe=""), esc(nom))
        )
    actions_html = '<div class="cat-actions">%s</div>' % "".join(actions) if actions else ""
    return (
        '<article class="cat-card" id="%s"><div class="cat-photo">%s</div><div class="cat-body">'
        '<div class="cat-name-row"><h3>%s</h3>%s</div><span class="cattery">%s</span>'
        '<dl class="cat-facts"><div><dt>Couleur</dt><dd>%s</dd></div><div><dt>Lignée</dt><dd>%s</dd></div>'
        '<div><dt>Date de naissance</dt><dd>%s</dd></div>%s</dl>'
        '<p class="cat-character">« %s »</p>'
        '<p class="cat-parents"><strong>Père :</strong> %s<br><strong>Mère :</strong> %s</p>%s</div></article>'
        % (
            slugify(nom), photo, name, price, esc(cat.get("chatterie_origine") or ""),
            esc(cat.get("couleur") or ""), esc(cat.get("lignee") or ""), esc(cat.get("date_naissance") or ""), titre,
            esc(cat.get("caractere") or ""), esc(cat.get("pere") or ""), esc(cat.get("mere") or ""), actions_html,
        )
    )


def build_cat_lists(data):
    for key, is_male in (("reproductrices", False), ("reproducteurs", True)):
        path = DIST / ("%s.html" % key)
        cats = [c for c in data[key].get(key, []) if is_visible(c)]
        cards = "".join(render_cat_card(c, is_male, i) for i, c in enumerate(cats))
        page, count = fill_grid(path.read_text(encoding="utf-8"), "%s-grid" % key, cards)
        if count:
            path.write_text(page, encoding="utf-8")
        else:
            print("[%s] grille introuvable : fiches laissées au JavaScript" % key)


def kittens_of(data, nom):
    return [c for c in data["chatons"].get("chatons", [])
            if c.get("url") and nom and (c.get("pere") == nom or c.get("mere") == nom)]


def render_mini_card(chaton):
    photo = '<img src="%s" alt="%s" loading="lazy">' % (esc(chaton["photo"]), esc(chaton.get("nom", ""))) if chaton.get("photo") else ""
    details = " · ".join(esc(v) for v in (chaton.get("sexe"), chaton.get("couleur")) if v)
    return (
        '<a class="sibling-card" href="%s"><div class="sibling-photo">%s</div><div class="sibling-body">'
        '<span class="%s">%s</span><h4>%s</h4><span>%s</span></div></a>'
        % (esc(chaton["url"]), photo, status_class(chaton, "sibling-status-inline"),
           esc(chaton.get("statut") or "Disponible"), esc(chaton.get("nom", "")), details)
    )


def build_parent_pages(data, md, waitlist):
    template = (DIST / "chaton.html").read_text(encoding="utf-8")
    urls = []
    for key, is_male in (("reproductrices", False), ("reproducteurs", True)):
        list_href = "%s.html" % key
        list_label = "Nos Reproducteurs" if is_male else "Nos Reproductrices"
        for cat in data[key].get(key, []):
            url = cat.get("url")
            if not url:
                continue
            nom = cat["nom"]
            couleur = text_of(cat.get("couleur"))
            role = "mâle reproducteur" if is_male else "chatte reproductrice"
            born = text_of(cat.get("date_naissance"))
            photos = photo_list(cat)

            facts = []
            if couleur:
                facts.append(quick_fact("fa-palette", "Couleur", esc(couleur)))
            if cat.get("lignee"):
                facts.append(quick_fact("fa-seedling", "Lignée", esc(cat["lignee"])))
            if born:
                facts.append(quick_fact("fa-cake-candles", "Né le" if is_male else "Née le", esc(born), True))
            if cat.get("titre"):
                # Le libellé dit déjà « Exposition » : on ne répète pas « Résultats d'exposition : ».
                titre = re.sub(r"^\s*résultats?\s+d['’]exposition\s*:\s*", "", cat["titre"], flags=re.I)
                facts.append(quick_fact("fa-award", "Exposition", esc(titre or cat["titre"]), True))
            if cat.get("pere") or cat.get("mere"):
                facts.append(quick_fact(
                    "fa-scroll", "Parents",
                    " × ".join(esc(v) for v in (cat.get("pere"), cat.get("mere")) if v), True,
                ))
            if is_male and cat.get("prix_saillie"):
                facts.append(quick_fact("fa-tag", "Saillie", "%s&nbsp;€" % esc(cat["prix_saillie"]), True))

            if is_male:
                cta = (
                    '<a href="contact.html?sujet=saillie&nom=%s" class="btn btn-primary">Demander une saillie avec %s</a>'
                    '<a href="chatons.html" class="btn btn-outline">Voir les chatons</a>' % (quote(nom, safe=""), esc(nom))
                )
            else:
                cta = (
                    '<a href="chatons.html" class="btn btn-primary">Voir les chatons disponibles</a>'
                    '<a href="liste-attente.html" class="btn btn-outline">Rejoindre la liste d\'attente</a>'
                )
            origine = '<span class="fiche-name-sub">%s</span>' % esc(cat["chatterie_origine"]) if cat.get("chatterie_origine") else ""
            tagline = '<p class="fiche-tagline">« %s »</p>' % esc(text_of(cat["caractere"])) if text_of(cat.get("caractere")) else ""
            badge = '<span class="fiche-sex-badge"><i class="fa-solid %s"></i></span>' % ("fa-mars" if is_male else "fa-venus")
            sections = [
                '<section class="section section-light"><div class="container"><div class="fiche-hero-grid">%s'
                '<h1 class="fiche-name">%s%s</h1><div class="fiche-hero-info">%s<div class="quick-facts">%s</div>'
                '<div class="cta-row">%s</div></div></div></div></section>'
                % (gallery_html(photos, cat_alt(nom, is_male), badge), esc(nom), origine, tagline, "".join(facts), cta)
            ]

            presentation = text_of(cat.get("presentation"))
            if presentation:
                rendered = md.render(presentation) if md is not None else "<p>%s</p>" % esc(presentation)
                sections.append(
                    '<section class="section section-light fiche-block"><div class="container">'
                    '<div class="section-head"><span class="kicker">Portrait</span><h2>À propos %s</h2></div>'
                    '<div class="article-body">%s</div></div></section>' % (esc(de_nom(nom)), rendered)
                )

            tests = [t for t in (cat.get("tests_sante") or []) if isinstance(t, dict) and text_of(t.get("test"))]
            if tests:
                rows = "".join(
                    '<div><dt>%s</dt><dd>%s</dd></div>' % (esc(text_of(t["test"])), esc(text_of(t.get("resultat")) or "—"))
                    for t in tests
                )
                sections.append(
                    '<section class="section section-alt"><div class="container" style="max-width:820px">'
                    '<div class="section-head"><span class="kicker">Santé</span><h2>Tests de santé %s</h2></div>'
                    '<dl class="health-list">%s</dl></div></section>' % (esc(de_nom(nom)), rows)
                )

            portee = text_of(waitlist.get("prochaine_portee"))
            parents_portee = text_of(waitlist.get("parents"))
            if portee and slugify(nom) in slugify(parents_portee).split("-"):
                sections.append(
                    '<section class="section section-dark" style="text-align:center"><div class="container">'
                    '<div class="section-head"><span class="kicker">Prochaine portée</span><h2>%s</h2>'
                    '<p>%s</p></div><a href="liste-attente.html" class="btn btn-primary">Être prévenu(e) en premier</a>'
                    '</div></section>' % (esc(portee), esc(parents_portee.replace(" x ", " × ")))
                )

            kittens = kittens_of(data, nom)
            if kittens:
                sections.append(
                    '<section class="section section-alt"><div class="container"><div class="section-head">'
                    '<span class="kicker">Descendance</span><h2>Ses chatons</h2></div>'
                    '<div class="siblings-row">%s</div></div></section>' % "".join(render_mini_card(c) for c in kittens)
                )

            sections.append(
                '<section class="section section-light" style="text-align:center"><div class="container">'
                '<a href="%s" class="btn btn-outline">← %s</a></div></section>' % (list_href, list_label)
            )

            title = seo_title("%s, Maine Coon %s%s" % (nom, "mâle" if is_male else "femelle", (" " + couleur) if couleur else ""))
            parts = [text_of(cat.get("caractere"))]
            parts.append("%s, %s Maine Coon%s%s%s." % (
                nom, role, (" " + couleur) if couleur else "",
                (", %s le %s" % ("né" if is_male else "née", born)) if born else "",
                (", lignée %s" % cat["lignee"].lower()) if cat.get("lignee") else "",
            ))
            parts.append("Élevage familial à Le Soler, près de Perpignan.")
            desc = truncate(" ".join(p for p in parts if p))
            image = abs_url(photos[0]) if photos else abs_url(DEFAULT_OG_IMAGE)
            jsonld = [breadcrumb([("Accueil", "/"), (list_label, "/" + list_href), (nom, url)])]
            page = shell_page(template, '<main id="fiche-parent">%s</main>' % "".join(sections), list_href)
            page = apply_head(page, title, desc, head_block(title, desc, url, image, jsonld=jsonld))
            out_dir = DIST / url.strip("/")
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "index.html").write_text(page, encoding="utf-8")
            urls.append(url)
    print("[parents] %d page(s) générée(s)" % len(urls))
    return urls


# --------------------------------------------------------------------------- chatons

def kitten_alt(chaton):
    return re.sub(r"\s+", " ", "%s, chaton Maine Coon %s %s" % (
        chaton.get("nom", ""), (chaton.get("sexe") or "").lower(), chaton.get("couleur") or "")).strip()


def render_kitten_card(chaton, index=0):
    nom = chaton.get("nom") or ""
    href = esc(chaton.get("url") or "chaton.html?nom=%s" % quote(nom, safe=""))
    photo = (
        '<img src="%s" alt="%s"%s>' % (esc(chaton["photo"]), esc(kitten_alt(chaton)), ' loading="lazy"' if index > 2 else "")
        if chaton.get("photo") else PAW_SVG
    )
    return (
        '<article class="kitten-card"><a href="%s" class="kitten-photo" aria-label="Voir la fiche de %s">'
        '<span class="%s">%s</span>%s</a><div class="kitten-body"><h3>%s</h3><ul class="kitten-facts">'
        '<li><strong>Sexe :</strong> %s</li><li><strong>Couleur :</strong> %s</li>'
        '<li><strong>Date de naissance :</strong> %s</li><li><strong>Prix :</strong> %s</li></ul>'
        '<div class="kitten-actions"><a href="%s" class="btn btn-outline btn-block">Voir sa fiche</a>'
        '<a href="contact.html?sujet=adoption&nom=%s" class="btn btn-primary btn-block">Je suis intéressé(e)</a></div>'
        '</div></article>'
        % (
            href, esc(nom), status_class(chaton), esc(chaton.get("statut") or "Disponible"), photo, esc(nom),
            esc(chaton.get("sexe") or "à préciser"), esc(chaton.get("couleur") or "à préciser"),
            esc(chaton.get("date_naissance") or "à préciser"), esc(chaton.get("prix") or "nous consulter"),
            href, quote(nom, safe=""),
        )
    )


def render_adopted_card(chaton, index=0):
    nom = chaton.get("nom") or ""
    href = esc(chaton["url"])
    photo = (
        '<img src="%s" alt="%s"%s>' % (esc(chaton["photo"]), esc(kitten_alt(chaton)), ' loading="lazy"' if index > 2 else "")
        if chaton.get("photo") else PAW_SVG
    )
    facts = []
    details = " · ".join(v for v in (chaton.get("sexe"), chaton.get("couleur")) if v)
    if details:
        facts.append("<li>%s</li>" % esc(details))
    if chaton.get("date_naissance"):
        facts.append("<li><strong>%s :</strong> %s</li>" % ("Née le" if chaton.get("sexe") == "Femelle" else "Né le", esc(chaton["date_naissance"])))
    if chaton.get("pere") and chaton.get("mere"):
        facts.append("<li><strong>Parents :</strong> %s × %s</li>" % (esc(chaton["pere"]), esc(chaton["mere"])))
    quote_html = family_quote(chaton)
    return (
        '<article class="kitten-card"><a href="%s" class="kitten-photo" aria-label="Voir la fiche de %s">'
        '<span class="%s">%s</span>%s</a><div class="kitten-body"><h3>%s</h3><ul class="kitten-facts">%s</ul>%s'
        '<div class="kitten-actions"><a href="%s" class="btn btn-outline btn-block">Voir sa fiche</a></div></div></article>'
        % (href, esc(nom), status_class(chaton), esc(chaton.get("statut") or "Adopté"), photo, esc(nom),
           "".join(facts), quote_html, href)
    )


def family_quote(chaton):
    quote_text = text_of(chaton.get("temoignage"))
    if not quote_text:
        return ""
    author = text_of(chaton.get("temoignage_auteur"))
    return '<blockquote class="family-quote"><p>« %s »</p>%s</blockquote>' % (
        esc(quote_text), "<cite>%s</cite>" % esc(author) if author else "")


def wa_link(nom):
    return "https://wa.me/%s?text=%s" % (WHATSAPP, quote("Bonjour, je suis intéressé(e) par %s 🐾" % nom, safe=""))


def render_parent_slot(label, nom, match):
    if not match:
        return (
            '<div class="parent-card"><div class="parent-unknown">%s</div><div class="parent-body">'
            '<span class="cattery">%s</span><h4>%s</h4></div></div>' % (PAW_SVG, esc(label), esc(nom))
        )
    cat, is_male = match
    href = cat.get("url") or "%s#%s" % ("reproducteurs.html" if is_male else "reproductrices.html", slugify(cat["nom"]))
    photo = '<img src="%s" alt="%s" loading="lazy">' % (esc(cat["photo"]), esc(cat_alt(cat["nom"], is_male))) if cat.get("photo") else ""
    caractere = '<p class="cat-character">« %s »</p>' % esc(cat["caractere"].strip()) if text_of(cat.get("caractere")) else ""
    more = '<a href="%s" class="teaser-link">Voir sa fiche →</a>' % esc(href) if cat.get("url") else ""
    return (
        '<div class="parent-card"><div class="parent-photo"><span class="parent-label">%s</span>%s</div>'
        '<div class="parent-body"><h4><a href="%s">%s</a></h4><span class="cattery">%s</span>'
        '<ul class="kitten-facts"><li><strong>Couleur :</strong> %s</li><li><strong>Lignée :</strong> %s</li></ul>%s%s</div></div>'
        % (esc(label), photo, esc(href), esc(cat["nom"]), esc(cat.get("chatterie_origine") or ""),
           esc(cat.get("couleur") or "à préciser"), esc(cat.get("lignee") or "à préciser"), caractere, more)
    )


def format_siren(value):
    digits = re.sub(r"\D", "", str(value))
    if len(digits) == 9:
        return "%s %s %s" % (digits[:3], digits[3:6], digits[6:])
    if len(digits) == 14:
        return "%s %s %s %s" % (digits[:3], digits[3:6], digits[6:9], digits[9:])
    return text_of(value)


def legal_line(chaton, parents, settings):
    """Mentions obligatoires d'une annonce de chat : affichées seulement si elles ont été saisies dans l'admin."""
    items = []
    if text_of(settings.get("siren")):
        items.append("SIREN %s" % esc(format_siren(settings["siren"])))
    try:
        count = int(chaton.get("portee_nombre") or 0)
    except (TypeError, ValueError):
        count = 0
    if count > 0:
        items.append("Portée de %d chaton%s" % (count, "s" if count > 1 else ""))
    mother = parents.get(chaton.get("mere") or "")
    if mother and text_of(mother[0].get("identification")):
        items.append("Mère identifiée sous le n° %s" % esc(text_of(mother[0]["identification"])))
    if text_of(settings.get("livre_genealogique")):
        items.append(esc(text_of(settings["livre_genealogique"])))
    if not items:
        return ""
    return '<p class="legal-line"><strong>Informations légales :</strong> %s</p>' % " · ".join(items)


def render_kitten_fiche(chaton, parents, all_kittens, settings):
    nom = chaton.get("nom") or ""
    female = chaton.get("sexe") == "Femelle"
    adopted = is_adopted(chaton)
    reserved = is_reserved(chaton)
    sex_icon = "fa-venus" if female else "fa-mars"
    badges = '<span class="%s">%s</span><span class="fiche-sex-badge"><i class="fa-solid %s"></i></span>' % (
        status_class(chaton), esc(chaton.get("statut") or "Disponible"), sex_icon)
    alt = "%s, chaton Maine Coon %s" % (nom, "adopté" if adopted else "disponible à l'adoption")
    born_raw = text_of(chaton.get("date_naissance"))
    born = parse_fr_date(born_raw)
    date_value = esc(born_raw) if born_raw else "à préciser"
    if born and not adopted:
        date_value += '<span data-birth="%s"></span>' % esc(born_raw)
    ready = ""
    if born and not adopted:
        ready_date = born + datetime.timedelta(days=84)
        ready = (
            '<div class="qf-divider"></div><div><span class="qf-label">Prêt à partir du</span>'
            '<span class="qf-value">%d %s %d</span></div>' % (ready_date.day, MONTHS[ready_date.month - 1], ready_date.year)
        )
    tagline = '<p class="fiche-tagline">« %s »</p>' % esc(chaton["tagline"]) if text_of(chaton.get("tagline")) else ""
    contact_href = "contact.html?sujet=adoption&nom=%s" % quote(nom, safe="")
    traits = chaton.get("traits") if isinstance(chaton.get("traits"), list) else []
    traits_html = (
        '<div class="trait-tags">%s</div>' % "".join(
            '<span class="trait-tag"><i class="fa-solid fa-paw"></i> %s</span>' % esc(t) for t in traits)
        if traits else ""
    )
    facts = [
        quick_fact(sex_icon, "Sexe", esc(chaton.get("sexe") or "à préciser")),
        quick_fact("fa-palette", "Couleur", esc(chaton.get("couleur") or "à préciser")),
        '<div class="quick-fact full"><span class="qf-icon"><i class="fa-solid fa-cake-candles"></i></span>'
        '<div class="qf-stack"><div><span class="qf-label">%s</span><span class="qf-value">%s</span></div>%s</div></div>'
        % ("Née le" if female else "Né le", date_value, ready),
    ]
    if not adopted:
        facts.append(quick_fact("fa-tag", "Prix", esc(chaton.get("prix") or "nous consulter"), True))

    buttons = (
        '<a href="%s" class="btn btn-primary">Je suis intéressé(e) par %s</a>'
        '<a href="%s" target="_blank" rel="noopener" class="btn btn-whatsapp"><i class="fa-brands fa-whatsapp"></i> WhatsApp</a>'
        % (contact_href, esc(nom), esc(wa_link(nom)))
    )
    if adopted:
        hero_cta = (
            '<p class="form-note adopted-note">%s a rejoint sa famille.</p>%s'
            '<div class="cta-row"><a href="liste-attente.html" class="btn btn-primary">Rejoindre la liste d\'attente</a>'
            '<a href="chatons.html" class="btn btn-outline">Voir les chatons disponibles</a></div>'
            % (esc(nom), family_quote(chaton))
        )
    else:
        hero_cta = '<div class="cta-row">%s</div>' % buttons
        if reserved:
            hero_cta += (
                '<p class="form-note" style="margin-top:1rem">%s est réservé%s. <a href="liste-attente.html" '
                'style="text-decoration:underline">Rejoignez la liste d\'attente</a> pour être prévenu(e) en priorité '
                'en cas de désistement ou à la prochaine portée.</p>' % (esc(nom), "e" if female else "")
            )

    trust = "".join(
        '<div class="trust-item-mini"><span class="ti-icon"><i class="fa-solid %s"></i></span><span>%s</span></div>' % item
        for item in (("fa-scroll", "Pedigree"), ("fa-syringe", "Vacciné"), ("fa-pump-soap", "Vermifugé"),
                     ("fa-microchip", "Identifié (puce)"), ("fa-gift", "Kit de départ"))
    )
    sections = [
        '<section class="section section-light"><div class="container"><div class="fiche-hero-grid">%s'
        '<h1 class="fiche-name">%s</h1><div class="fiche-hero-info">%s<div class="quick-facts">%s</div>%s%s</div></div>'
        '<div class="trust-strip-mini">%s</div>%s</div></section>'
        % (gallery_html(photo_list(chaton), alt, badges), esc(nom), tagline, "".join(facts), traits_html, hero_cta,
           trust, legal_line(chaton, parents, settings))
    ]

    if chaton.get("pere") or chaton.get("mere"):
        slots = "".join(
            render_parent_slot(label, chaton[key], parents.get(chaton[key]))
            for label, key in (("Père", "pere"), ("Mère", "mere")) if chaton.get(key)
        )
        sections.append(
            '<section class="section section-light"><div class="container"><div class="section-head">'
            '<span class="kicker">Origines</span><h2>Ses parents</h2></div><div class="grid grid-2">%s</div></div></section>' % slots
        )

    siblings = [
        c for c in all_kittens
        if c.get("url") and c.get("nom") != nom and chaton.get("pere") and chaton.get("mere")
        and c.get("pere") == chaton.get("pere") and c.get("mere") == chaton.get("mere")
    ]
    if siblings:
        sections.append(
            '<section class="section section-alt"><div class="container"><div class="section-head">'
            '<span class="kicker">Même portée</span><h2>Ses frères et sœurs</h2></div>'
            '<div class="siblings-row">%s</div></div></section>' % "".join(render_mini_card(c) for c in siblings)
        )

    if adopted:
        sections.append(
            '<section class="section section-alt" style="text-align:center"><div class="container">'
            '<h2>Envie d\'un chaton de la même lignée ?</h2>'
            '<p style="max-width:520px;margin:0 auto 1.6rem">Inscrivez-vous sur la liste d\'attente : vous serez '
            'prévenu(e) en premier de la prochaine portée, sans engagement.</p>'
            '<div class="cta-row" style="justify-content:center;margin-bottom:1.6rem">'
            '<a href="liste-attente.html" class="btn btn-primary">Rejoindre la liste d\'attente</a>'
            '<a href="chatons.html" class="btn btn-outline">Voir les chatons disponibles</a></div>'
            '<a href="chatons-adoptes/" style="text-decoration:underline">← Tous les chatons adoptés</a></div></section>'
        )
        return "".join(sections)

    steps = (
        ("Prise de contact", "Vous nous parlez de votre projet, on répond à toutes vos questions."),
        ("Rencontre", "En visio ou à la chatterie au Soler, pour faire connaissance avec %s." % esc(nom)),
        ("Réservation", "Des arrhes de 300 € valident votre réservation jusqu'au départ du chaton."),
        ("Départ", "Remise dès 12 semaines, avec pedigree, carnet de santé et kit de départ."),
    )
    sections.append(
        '<section class="section section-dark"><div class="container"><div class="section-head">'
        '<span class="kicker">Étapes</span><h2>Comment se passe l\'adoption ?</h2></div><div class="process-steps">%s</div>'
        '</div></section>' % "".join(
            '<div class="process-step"><div class="process-num">%d</div><h4>%s</h4><p>%s</p></div>' % (i + 1, title, text)
            for i, (title, text) in enumerate(steps)
        )
    )
    sections.append(
        '<section class="section section-alt" style="text-align:center"><div class="container">'
        '<h2>Vous craquez pour %s ?</h2>'
        '<p style="max-width:520px;margin:0 auto 1.6rem">Vous avez une question, un coup de cœur ? Nous serons ravis '
        'd\'échanger avec vous.</p><div class="cta-row" style="justify-content:center;margin-bottom:1.6rem">%s</div>'
        '<p style="margin:0 0 1.2rem"><a href="liste-attente.html" style="text-decoration:underline">Ce n\'est pas le bon '
        'moment ? Rejoignez la liste d\'attente.</a></p>'
        '<a href="chatons.html" class="btn btn-outline">← Voir tous les chatons disponibles</a></div></section>' % (esc(nom), buttons)
    )
    return "".join(sections)


def build_kittens(data, settings):
    chatons = data["chatons"].get("chatons", [])
    parents = parent_index(data)
    template = (DIST / "chaton.html").read_text(encoding="utf-8")
    urls = []
    for chaton in chatons:
        url = chaton.get("url")
        if not url:
            continue
        nom = chaton["nom"]
        female = chaton.get("sexe") == "Femelle"
        adopted = is_adopted(chaton)
        sexe_label = "femelle" if female else "mâle"
        couleur = text_of(chaton.get("couleur"))
        statut = (chaton.get("statut") or "Disponible").lower()
        if female and statut in ("réservé", "adopté"):
            statut += "e"
        born = chaton.get("date_naissance")
        sentence = "Chaton Maine Coon %s%s%s, %s." % (
            sexe_label, (" " + couleur) if couleur else "",
            (", %s le %s" % ("née" if female else "né", born)) if born else "", statut,
        )
        tagline = text_of(chaton.get("tagline"))
        desc = truncate("%s%s Élevage familial à Le Soler, près de Perpignan." % ((tagline + ". ") if tagline else "", sentence))
        title = seo_title("%s, chaton Maine Coon %s%s" % (nom, sexe_label, (" " + couleur) if couleur else ""))
        photo = chaton.get("photo")
        image = abs_url(photo) if photo else abs_url(DEFAULT_OG_IMAGE)
        crumbs = (
            [("Accueil", "/"), ("Chatons adoptés", "/chatons-adoptes/"), (nom, url)] if adopted
            else [("Accueil", "/"), ("Chatons disponibles", "/chatons.html"), (nom, url)]
        )
        page = apply_head(template, title, desc, head_block(title, desc, url, image, jsonld=[breadcrumb(crumbs)]))
        fiche = (
            '<main id="fiche-chaton" data-nom="%s" data-prerendered="true">%s</main>'
            % (esc(nom), render_kitten_fiche(chaton, parents, chatons, settings))
        )
        page = re.sub(r'<main id="fiche-chaton">.*?</main>', lambda m: fiche, page, count=1, flags=re.S)
        out_dir = DIST / url.strip("/")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(page, encoding="utf-8")
        urls.append(url)
    print("[chatons] %d page(s) générée(s)" % len(urls))
    return urls


def build_kitten_list(data):
    """Liste des chatons disponibles + galerie des adoptés (créée seulement s'il y en a)."""
    chatons = [c for c in data["chatons"].get("chatons", []) if is_visible(c)]
    available = [c for c in chatons if not is_adopted(c)]
    adopted = [c for c in chatons if is_adopted(c) and c.get("url")]
    path = DIST / "chatons.html"
    page, count = fill_grid(path.read_text(encoding="utf-8"), "kittens-grid",
                            "".join(render_kitten_card(c, i) for i, c in enumerate(available)))
    if not count:
        print("[chatons] grille introuvable : fiches laissées au JavaScript")
        page = path.read_text(encoding="utf-8")
    if adopted:
        page = page.replace(
            "<!-- chatons-adoptes -->",
            '<p class="adopted-link"><a href="chatons-adoptes/">Ils ont trouvé leur famille : voir nos chatons déjà adoptés →</a></p>',
            1,
        )
    path.write_text(page, encoding="utf-8")
    if not adopted:
        return []

    url = "/chatons-adoptes/"
    title = seo_title("Chatons Maine Coon adoptés")
    desc = truncate(
        "Ils ont trouvé leur famille : les chatons Maine Coon nés à la Chatterie Epic Claws et déjà adoptés. "
        "Élevage familial à Le Soler, près de Perpignan."
    )
    main = (
        '<main id="chatons-adoptes"><section class="page-banner"><div class="container">'
        '<h1>Ils ont trouvé leur famille</h1><p>Les chatons nés à la chatterie qui ont rejoint leur nouveau foyer.</p>'
        '</div></section><section class="section section-light"><div class="container">'
        '<div class="grid grid-3">%s</div>'
        '<div class="waitlist-teaser"><h3>Vous aimeriez être les prochains ?</h3>'
        '<p>Rejoignez la liste d\'attente : vous serez prévenu(e) en premier des prochaines naissances, sans engagement.</p>'
        '<a href="liste-attente.html" class="btn btn-primary">Rejoindre la liste d\'attente</a></div>'
        '</div></section></main>' % "".join(render_adopted_card(c, i) for i, c in enumerate(adopted))
    )
    template = (DIST / "chaton.html").read_text(encoding="utf-8")
    image = abs_url(adopted[0]["photo"]) if adopted[0].get("photo") else abs_url(DEFAULT_OG_IMAGE)
    jsonld = [breadcrumb([("Accueil", "/"), ("Chatons disponibles", "/chatons.html"), ("Chatons adoptés", url)])]
    gallery = apply_head(shell_page(template, main, "chatons.html"), title, desc,
                         head_block(title, desc, url, image, jsonld=jsonld))
    out_dir = DIST / "chatons-adoptes"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(gallery, encoding="utf-8")
    print("[adoptés] galerie générée (%d chaton(s))" % len(adopted))
    return [url]


# --------------------------------------------------------------------------- réglages du site

def build_legal(settings):
    """Complète l'identité de l'éditeur dans les mentions légales avec ce qui est saisi dans l'admin."""
    path = DIST / "mentions-legales.html"
    if not path.exists():
        return
    rows = [("Site", "Chatterie Epic Claws, élevage de chats Maine Coon")]
    for label, key in (("Responsable de la publication", "nom_eleveur"), ("Statut", "statut_juridique")):
        if text_of(settings.get(key)):
            rows.append((label, esc(text_of(settings[key]))))
    if text_of(settings.get("siren")):
        rows.append(("SIREN", esc(format_siren(settings["siren"]))))
    adresse = text_of(settings.get("adresse"))
    rows.append(("Adresse", esc(adresse).replace("\n", "<br>") if adresse else "Le Soler (66270), Pyrénées-Orientales, France"))
    rows.append(("Téléphone", '<a href="tel:+33685499971">+33 6 85 49 99 71</a>'))
    email = text_of(settings.get("email"))
    if email:
        rows.append(("E-mail", '<a href="mailto:%s">%s</a>' % (esc(email), esc(email))))
    extras = [text_of(settings.get(key)) for key in ("livre_genealogique", "mention_libre")]
    extras = [e for e in extras if e]
    block = '<dl class="legal-identity">%s</dl>' % "".join("<div><dt>%s</dt><dd>%s</dd></div>" % row for row in rows)
    if extras:
        block += "".join("<p>%s</p>" % esc(e).replace("\n", "<br>") for e in extras)
    page = path.read_text(encoding="utf-8")
    page, count = re.subn(r'<div id="legal-identity">.*?</div>', lambda m: '<div id="legal-identity">%s</div>' % block,
                          page, count=1, flags=re.S)
    if count:
        path.write_text(page, encoding="utf-8")


def spots_text(restantes, total):
    if restantes == 0:
        return "liste complète, inscription en liste de réserve"
    if restantes == 1:
        return "plus qu'une place sur %d" % total
    return "plus que %d places sur %d" % (restantes, total)


def to_count(value):
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def live_signup_count():
    """Nombre d'inscrits au moment de la publication (le navigateur le rafraîchit ensuite)."""
    try:
        request = Request(SITE + "/api/places", headers={"User-Agent": "epic-claws-build"})
        with urlopen(request, timeout=5) as response:
            return to_count(json.loads(response.read().decode("utf-8")).get("count"))
    except Exception as exc:
        print("[bandeau] nombre d'inscrits indisponible (%s) : complété dans le navigateur" % exc.__class__.__name__)
        return None


def litter_banner(waitlist):
    portee = text_of(waitlist.get("prochaine_portee"))
    if not portee:
        return ""
    parents = text_of(waitlist.get("parents")).replace(" x ", " × ").replace(" X ", " × ")
    total = to_count(waitlist.get("places_total"))
    prises = to_count(waitlist.get("places_deja_prises")) or 0
    attrs, spots = "", ""
    if total:
        attrs = ' data-total="%d" data-prises="%d"' % (total, prises)
        count = live_signup_count()
        label = spots_text(max(0, total - prises - count), total) if count is not None else ""
        spots = '<span class="lb-spots">%s</span>' % esc(label)
    return (
        '<a class="litter-banner" href="liste-attente.html"%s><span class="lb-main">Prochaine portée : <strong>%s</strong></span>'
        '%s%s<span class="lb-cta">Je m\'inscris →</span></a>'
        % (attrs, esc(portee), '<span class="lb-parents">%s</span>' % esc(parents) if parents else "", spots)
    )


NO_BANNER = {"liste-attente.html", "merci-liste-attente.html", "merci.html", "404.html", "article.html", "chaton.html"}


def finish_pages(settings, waitlist):
    """Dernière passe sur toutes les pages publiques : bandeau, SIREN du pied de page, code Search Console."""
    banner = litter_banner(waitlist)
    siren = format_siren(settings["siren"]) if text_of(settings.get("siren")) else ""
    code = text_of(settings.get("google_site_verification"))
    match = re.search(r'content="([^"]+)"', code)
    code = match.group(1) if match else code
    touched = 0
    for path in DIST.rglob("*.html"):
        rel = path.relative_to(DIST).as_posix()
        if rel.startswith("admin/"):
            continue
        page = original = path.read_text(encoding="utf-8")
        if banner and rel not in NO_BANNER and "litter-banner" not in page:
            page = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + "\n" + banner, page, count=1)
        if siren:
            page = page.replace("<!--siren-->", " · SIREN %s" % esc(siren))
        if code and rel == "index.html":
            page = page.replace("</head>", '<meta name="google-site-verification" content="%s">\n</head>' % esc(code), 1)
        if page != original:
            path.write_text(page, encoding="utf-8")
            touched += 1
    print("[finitions] %d page(s) complétée(s)%s" % (touched, " avec le bandeau" if banner else ""))


# --------------------------------------------------------------------------- sitemap

def build_sitemap(article_urls, other_urls):
    static = ["/", "/chatons.html", "/reproductrices.html", "/reproducteurs.html", "/articles.html", "/contact.html"]
    if (DIST / "liste-attente.html").exists():
        static.insert(2, "/liste-attente.html")
    rows = ["  <url><loc>%s</loc></url>" % esc(SITE + p) for p in static]
    for url, date in article_urls or []:
        lastmod = "<lastmod>%s</lastmod>" % esc(date) if date else ""
        rows.append("  <url><loc>%s</loc>%s</url>" % (esc(SITE + url), lastmod))
    for url in other_urls or []:
        rows.append("  <url><loc>%s</loc></url>" % esc(SITE + url))
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s\n</urlset>\n' % "\n".join(rows)
    (DIST / "sitemap.xml").write_text(xml, encoding="utf-8")
    print("[sitemap] %d URL(s)" % len(rows))


# --------------------------------------------------------------------------- main

def main():
    copy_site()
    data_dir = DIST / "data"
    names = ("chatons", "reproductrices", "reproducteurs", "articles")
    data = {}
    loaded = set()
    for name in names:
        try:
            data[name] = read_json(data_dir / ("%s.json" % name))
            loaded.add(name)
        except Exception as exc:
            print("[données] %s.json illisible (%s) : on le laisse tel quel" % (name, exc))
            data[name] = {name: []}
    settings = read_json_optional(data_dir / "reglages.json")
    waitlist = read_json_optional(data_dir / "liste-attente.json")

    optimize = make_optimizer()
    step("images", optimize_data, data, optimize)
    step("adresses", assign_urls, data)

    article_urls = []
    try:
        md = make_markdown()
    except Exception:
        print("[ERREUR] markdown-it-py indisponible : pages d'articles ignorées")
        traceback.print_exc()
        md = None
    if md is not None:
        article_urls = step("articles", build_articles, data, md) or []
        step("liste des articles", build_article_list, data)
    other_urls = []
    other_urls += step("parents", build_parent_pages, data, md, waitlist) or []
    step("listes des parents", build_cat_lists, data)
    other_urls += step("chatons", build_kittens, data, settings) or []
    other_urls += step("liste des chatons", build_kitten_list, data) or []
    step("mentions légales", build_legal, settings)
    step("finitions", finish_pages, settings, waitlist)
    step("sitemap", build_sitemap, article_urls, other_urls)

    # Les brouillons d'articles ne sont pas publiés : on les retire aussi des données servies au navigateur.
    if "articles" in loaded:
        data["articles"]["articles"] = [a for a in data["articles"].get("articles", []) if is_visible(a)]
    # Les réglages ne servent qu'à ce script : inutile de les exposer tels quels.
    if (data_dir / "reglages.json").exists():
        (data_dir / "reglages.json").unlink()
    for name in names:
        if name in loaded:
            step("écriture %s.json" % name, write_json, data_dir / ("%s.json" % name), data[name])
    print("Build terminé.")


if __name__ == "__main__":
    main()
