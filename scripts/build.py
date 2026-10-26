#!/usr/bin/env python3
"""Build du site Chatterie Epic Claws (exécuté par Netlify à chaque déploiement).

1. Copie le site tel quel dans dist/.
2. Optimise les images référencées par le CMS (HEIC iPhone, PNG trop lourds...).
3. Génère une vraie page par article (/articles/<slug>/) et par chaton (/chatons/<slug>/)
   avec titre, description, aperçu de partage (Facebook/WhatsApp) et données Google.
4. Génère sitemap.xml.

Chaque étape est isolée : si l'une échoue, le site reste publiable (liens d'origine conservés).
Compatible Python 3.8+.
"""
import html
import json
import re
import shutil
import traceback
import unicodedata
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
SITE = "https://chatterieepicclaws.fr"
SITE_NAME = "Chatterie Epic Claws"
DEFAULT_OG_IMAGE = "/images/hero.jpg"
OPT_DIR = "images/optimized"

EXCLUDE_TOP = {
    ".git", ".github", ".claude", "dist", "scripts", "node_modules", "__pycache__",
    "requirements.txt", "requirements-images.txt", "netlify.toml", ".gitignore",
}


def esc(value):
    return html.escape(str(value), quote=True)


def slugify(value):
    text = unicodedata.normalize("NFKD", str(value).lower().replace("œ", "oe").replace("æ", "ae"))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


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


def optimize_data(data, optimize):
    for chaton in data["chatons"].get("chatons", []):
        if chaton.get("photo"):
            chaton["photo"] = optimize(chaton["photo"])
        extras = chaton.get("photos_supplementaires")
        if extras:
            chaton["photos_supplementaires"] = [
                optimize(p) if isinstance(p, str)
                else (dict(p, image=optimize(p["image"])) if isinstance(p, dict) and p.get("image") else p)
                for p in extras
            ]
    for key in ("reproductrices", "reproducteurs"):
        for cat in data[key].get(key, []):
            if cat.get("photo"):
                cat["photo"] = optimize(cat["photo"])
    for article in data["articles"].get("articles", []):
        if article.get("image"):
            article["image"] = optimize(article["image"], 1600)
        if article.get("corps"):
            article["corps"] = MD_IMAGE.sub(
                lambda m: m.group(1) + optimize(m.group(2), 1400) + m.group(3), article["corps"]
            )


# --------------------------------------------------------------------------- pages

def make_markdown():
    from markdown_it import MarkdownIt
    return MarkdownIt("commonmark", {"html": True, "linkify": False}).enable("table").enable("strikethrough")


def head_block(title, desc, path, image=None, og_type="website", jsonld=None):
    canonical = SITE + path
    lines = [
        '<link rel="canonical" href="%s">' % esc(canonical),
        '<meta name="robots" content="index, follow, max-image-preview:large">',
        '<meta property="og:locale" content="fr_FR">',
        '<meta property="og:site_name" content="%s">' % esc(SITE_NAME),
        '<meta property="og:type" content="%s">' % og_type,
        '<meta property="og:title" content="%s">' % esc(title),
        '<meta property="og:description" content="%s">' % esc(desc),
        '<meta property="og:url" content="%s">' % esc(canonical),
        '<meta name="twitter:card" content="summary_large_image">',
        '<meta name="twitter:title" content="%s">' % esc(title),
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


def article_card(article, url):
    bg = article.get("image") or "images/logo.avif"
    date = article.get("date", "")
    return (
        '<a class="teaser-card article-card" style="background-image:url(\'%s\')" href="%s">'
        '<div class="teaser-body"><span class="article-date">%s</span><h3>%s</h3><p>%s</p>'
        '<span class="teaser-link">Lire la suite →</span></div></a>'
        % (esc(bg), esc(url), esc(format_date(date)), esc(article.get("titre", "")), esc(article.get("extrait", "")))
    )


MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
          "septembre", "octobre", "novembre", "décembre"]


def format_date(date_str):
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", date_str or "")
    if not match:
        return date_str or ""
    year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
    return "%d %s %d" % (day, MONTHS[month - 1], year)


def build_articles(data, md):
    articles = data["articles"].get("articles", [])
    template = (DIST / "article.html").read_text(encoding="utf-8")
    template = template.replace(
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js"></script>\n', ""
    )
    used = set()
    pages = []
    for article in articles:
        slug_raw = article.get("slug") or article.get("titre") or ""
        base = slugify(slug_raw)
        if not base or not article.get("titre"):
            continue
        slug, n = base, 2
        while slug in used:
            slug, n = "%s-%d" % (base, n), n + 1
        used.add(slug)
        article["url"] = "/articles/%s/" % slug
        pages.append((slug, article))

    has_waitlist = (DIST / "liste-attente.html").exists()
    for slug, article in pages:
        url = article["url"]
        body = md.render(article.get("corps", ""))
        body = body.replace("<img ", '<img loading="lazy" decoding="async" ')
        title_text = article["titre"]
        desc_source = article.get("extrait") or plain_text(body)
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
                              "logo": {"@type": "ImageObject", "url": SITE + "/images/logo.avif"}},
                "mainEntityOfPage": {"@type": "WebPage", "@id": SITE + url},
            },
            {
                "@context": "https://schema.org", "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Accueil", "item": SITE + "/"},
                    {"@type": "ListItem", "position": 2, "name": "Nos Articles", "item": SITE + "/articles.html"},
                    {"@type": "ListItem", "position": 3, "name": title_text, "item": SITE + url},
                ],
            },
        ]
        full_title = "%s — %s" % (title_text, SITE_NAME)
        page = apply_head(page, full_title, desc, head_block(full_title, desc, url, image, "article", jsonld))

        others = [a for s, a in pages if a is not article]
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

        out_dir = DIST / "articles" / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(page, encoding="utf-8")
    print("[articles] %d page(s) générée(s)" % len(pages))
    return [(a["url"], a.get("date")) for _, a in pages]


def build_kittens(data):
    chatons = data["chatons"].get("chatons", [])
    template = (DIST / "chaton.html").read_text(encoding="utf-8")
    used = set()
    urls = []
    for chaton in chatons:
        nom = chaton.get("nom")
        if not nom or chaton.get("visible") is False:
            continue
        base = slugify(nom)
        if not base:
            continue
        slug, n = base, 2
        while slug in used:
            slug, n = "%s-%d" % (base, n), n + 1
        used.add(slug)
        url = "/chatons/%s/" % slug
        chaton["url"] = url

        female = chaton.get("sexe") == "Femelle"
        sexe_label = "femelle" if female else "mâle"
        couleur = (chaton.get("couleur") or "").strip()
        title = "%s, chaton Maine Coon %s%s — %s" % (nom, sexe_label, (" " + couleur) if couleur else "", SITE_NAME)
        statut = (chaton.get("statut") or "Disponible").lower()
        born = chaton.get("date_naissance")
        sentence = "Chaton Maine Coon %s%s%s, %s." % (
            sexe_label, (" " + couleur) if couleur else "",
            (", %s le %s" % ("née" if female else "né", born)) if born else "", statut,
        )
        tagline = (chaton.get("tagline") or "").strip()
        desc = truncate("%s%s Élevage familial à Le Soler, près de Perpignan." % ((tagline + ". ") if tagline else "", sentence))
        photo = chaton.get("photo")
        image = abs_url(photo) if photo else abs_url(DEFAULT_OG_IMAGE)
        page = apply_head(template, title, desc, head_block(title, desc, url, image))
        summary = (
            '<main id="fiche-chaton" data-nom="%s"><section class="section section-light"><div class="container">'
            '<h1>%s</h1><p>%s Chatterie Epic Claws, Le Soler (Pyrénées-Orientales).</p></div></section></main>'
            % (esc(nom), esc(nom), esc(sentence))
        )
        page = re.sub(r'<main id="fiche-chaton">.*?</main>', lambda m: summary, page, count=1, flags=re.S)
        out_dir = DIST / "chatons" / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(page, encoding="utf-8")
        urls.append(url)
    print("[chatons] %d page(s) générée(s)" % len(urls))
    return urls


# --------------------------------------------------------------------------- sitemap

def build_sitemap(article_urls, kitten_urls):
    static = ["/", "/chatons.html", "/reproductrices.html", "/reproducteurs.html", "/articles.html", "/contact.html"]
    if (DIST / "liste-attente.html").exists():
        static.insert(2, "/liste-attente.html")
    rows = ["  <url><loc>%s</loc></url>" % esc(SITE + p) for p in static]
    for url, date in article_urls or []:
        lastmod = "<lastmod>%s</lastmod>" % esc(date) if date else ""
        rows.append("  <url><loc>%s</loc>%s</url>" % (esc(SITE + url), lastmod))
    for url in kitten_urls or []:
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

    optimize = make_optimizer()
    step("images", optimize_data, data, optimize)

    article_urls, kitten_urls = [], []
    try:
        md = make_markdown()
    except Exception:
        print("[ERREUR] markdown-it-py indisponible : pages d'articles ignorées")
        traceback.print_exc()
        md = None
    if md is not None:
        article_urls = step("articles", build_articles, data, md) or []
    kitten_urls = step("chatons", build_kittens, data) or []
    step("sitemap", build_sitemap, article_urls, kitten_urls)

    for name in names:
        if name in loaded:
            step("écriture %s.json" % name, write_json, data_dir / ("%s.json" % name), data[name])
    print("Build terminé.")


if __name__ == "__main__":
    main()
