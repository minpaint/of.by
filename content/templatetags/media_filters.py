import re

from django import template
from django.utils.safestring import mark_safe


register = template.Library()

EMBED_ALLOW = (
    "accelerometer; autoplay; clipboard-write; encrypted-media; "
    "gyroscope; picture-in-picture; web-share"
)
EMBED_REFERRER_POLICY = "strict-origin-when-cross-origin"
EMBED_SRC_RE = re.compile(
    r"""src=(?P<quote>["'])(?P<src>https?://(?:www\.)?(?:youtube\.com|youtube-nocookie\.com|docs\.google\.com)/[^"']+)(?P=quote)""",
    re.IGNORECASE,
)
IFRAME_RE = re.compile(r"<iframe\b(?P<attrs>[^>]*)>", re.IGNORECASE)


@register.filter
def normalize_embeds(value, request=None):
    """Add browser-required attributes to trusted embedded media iframes."""
    if not value:
        return value

    def replace_iframe(match):
        attrs = match.group("attrs")
        src_match = EMBED_SRC_RE.search(attrs)
        if not src_match:
            return match.group(0)

        updated_attrs = attrs
        src = src_match.group("src")
        if "youtube.com/" in src or "youtube-nocookie.com/" in src:
            next_src = src.replace("https://www.youtube.com/embed/", "https://www.youtube-nocookie.com/embed/")
            next_src = next_src.replace("http://www.youtube.com/embed/", "https://www.youtube-nocookie.com/embed/")
            if "?" not in next_src:
                next_src = f"{next_src}?rel=0"
            elif "rel=" not in next_src:
                next_src = f"{next_src}&rel=0"
            if request is not None and "origin=" not in next_src:
                origin = f"{request.scheme}://{request.get_host()}"
                separator = "&" if "?" in next_src else "?"
                next_src = f"{next_src}{separator}origin={origin}"
            updated_attrs = updated_attrs.replace(src, next_src)

        if not re.search(r"\ballow\s*=", attrs, re.IGNORECASE):
            updated_attrs += f' allow="{EMBED_ALLOW}"'
        if not re.search(r"\breferrerpolicy\s*=", attrs, re.IGNORECASE):
            updated_attrs += f' referrerpolicy="{EMBED_REFERRER_POLICY}"'
        if not re.search(r"\bframeborder\s*=", attrs, re.IGNORECASE):
            updated_attrs += ' frameborder="0"'

        return f"<iframe{updated_attrs}>"

    return mark_safe(IFRAME_RE.sub(replace_iframe, str(value)))
