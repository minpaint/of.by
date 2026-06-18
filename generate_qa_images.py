"""
Генератор тематических SVG-иллюстраций для статей рубрики «Вопрос-ответ».

Использование:
    python generate_qa_images.py --all               # генерировать для ВСЕХ статей QA без картинок
    python generate_qa_images.py --ids 159 229       # только для указанных id
    python generate_qa_images.py --cat vopros-otvet  # вся подкатегория
    python generate_qa_images.py --dry-run           # показать, что бы сгенерировалось (без записи)
    python generate_qa_images.py --assign-existing   # привязать 5 ручных SVG из static/img/generated/qa/
    python generate_qa_images.py --all --limit 20     # генерировать, но не больше N штук
"""
import os
import sys
import math
import re
import argparse
from pathlib import Path

# Django bootstrap
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Q

from content.models import Category, ContentItem


# ──────────────────────────────────────────────
#  Тематические пресеты: ключевые слова → тема
# ──────────────────────────────────────────────

THEMES = [
    # (keywords, theme_key, accent, bg, line, dark, icon_func)
    (
        ['трудов', 'договор', 'нанимател', 'работник', 'занятост', 'увольнен',
         'отпуск', 'зарплат', 'оплата труд', 'заработн', 'контракт', 'приём',
         'прием на работ', 'трудовой спор', 'дисциплин'],
        'contract', '#4357C8', '#EEF2FF', '#6B7CE0', '#1A4FA0', 'icon_contract',
    ),
    (
        ['охрана труд', 'система управлен', 'политика в област',
         'служб по охран', 'инструктаж', 'обучен', 'проверка знани',
         'производственн', 'техника безопасн',
         'аттестац', 'компенсац', 'вредн', 'опасн'],
        'shield', '#2E9E6B', '#E8F3EE', '#5BB58A', '#1E7A52', 'icon_shield',
    ),
    (
        ['пожар', 'огн', 'пожаробезопасн', 'эвакуац', 'огнетушител', 'пожарн'],
        'fire', '#D94040', '#FDEEEC', '#E87A7A', '#A02E2E', 'icon_fire',
    ),
    (
        ['санитар', 'гигиен', 'медицин', 'оздоровлен', 'фактор',
         'вредн веществ', 'пыль', 'шум', 'вибрац', 'микроклимат', 'освещен',
         'санитарн', 'ветил'],
        'sanitary', '#5A9E4B', '#F1F5F0', '#7DB86C', '#3C7A2E', 'icon_sanitary',
    ),
    (
        ['рабочее мест', 'станок', 'оборудован', 'машин', 'конвейер',
         'цех', 'производств'],
        'workplace', '#3B6FB0', '#EAF1FB', '#6F94C6', '#234E86', 'icon_workplace',
    ),
    (
        ['шестерён', 'шестерн', 'процесс', 'технолог', 'агрегат', 'поточн', 'автоматиз'],
        'gears', '#6B5BB8', '#F3F0FA', '#9485CE', '#4A3D8F', 'icon_gears',
    ),
    (
        ['транспорт', 'автомобил', 'груз', 'перевозк', 'погруз', 'разгруз',
         'складир', 'дорожн', 'пассажир'],
        'transport', '#E08A2E', '#FEF5E8', '#F0B86E', '#A8661A', 'icon_transport',
    ),
    (
        ['строительств', 'здани', 'сооружен', 'кран', 'строительн',
         'ремонт', 'высотн'],
        'construction', '#C45A3C', '#FCF0EC', '#D88B74', '#8C3A22', 'icon_construction',
    ),
    (
        ['электр', 'тепло', 'установк', 'подстанц', 'кабел', 'провод',
         'высоковольтн', 'заземлен'],
        'electrical', '#D4A030', '#FDF6E3', '#E8C468', '#9A7520', 'icon_electrical',
    ),
    (
        ['радиац', 'ионизир', 'защита от излучен', 'дозиметр', 'рентген'],
        'radiation', '#B84EAD', '#F8EFF7', '#CE7DC8', '#7E2F76', 'icon_radiation',
    ),
    (
        ['лазер', 'оптическ'],
        'laser', '#3DB8A5', '#E8FAF6', '#76CCC0', '#268878', 'icon_laser',
    ),
    (
        ['средств индивидуальн', 'каск', 'респиратор', 'перчат',
         'защитн одежд', 'обувь защит', 'очки защит'],
        'ppe', '#E06880', '#FDF0F3', '#EE94A6', '#A84058', 'icon_ppe',
    ),
    (
        ['надзор', 'контроль', 'инспекц', 'проверк', 'госнадзор',
         'департамент', 'министерств'],
        'inspection', '#5A7EB8', '#EDF2F9', '#88A4D0', '#3A5A8A', 'icon_inspection',
    ),
    (
        ['нессчастн', 'несчастн', 'авари', 'травм', 'расследован',
         'профзаболеван', 'пострадавш'],
        'accident', '#D04060', '#FDF0F2', '#E07890', '#9A2A44', 'icon_accident',
    ),
    (
        ['страхован', 'страх', 'выплат', 'пособи'],
        'insurance', '#4E9A6B', '#EEF5F0', '#7CB894', '#2E6A42', 'icon_insurance',
    ),
    (
        ['чрезвычайн', 'ликвидац', 'гражданск оборон',
         'аварийн', 'катастроф', 'бедстви'],
        'emergency', '#E06040', '#FEF0EC', '#EE9478', '#A04028', 'icon_emergency',
    ),
    (
        ['психофизиолог', 'стресс', 'утомлен', 'микропауз', 'режим труд',
         'психолог', 'эмоционал'],
        'psychology', '#8B6BB0', '#F4F0F9', '#AB92C8', '#604080', 'icon_psychology',
    ),
    (
        ['законодат', 'нормативн', 'правов акт', 'кодекс', 'стандарт',
         'регулирован', 'правоотношен', 'правов норм', 'закона', 'правов',
         'стандартиз', 'подтвержден соответств', 'оценка соответств', 'техническ регламент'],
        'law', '#3A5A8A', '#EAF0F8', '#6B8AB8', '#243E66', 'icon_law',
    ),
    (
        ['права работающ', 'право на охран', 'обязанност', 'обязанности работ',
         'гаранти', 'компенсац', 'льгот', 'права и обязанност'],
        'rights', '#C77E3A', '#FBF1E8', '#DCA874', '#8E5520', 'icon_rights',
    ),
    (
        ['государственн управлен', 'орган управл', 'госкомитет', 'министерств',
         'ведомств', 'госнадзор', 'реестр', 'регистрац', 'государств'],
        'government', '#4A6A8E', '#ECF1F7', '#7B96B5', '#2E4868', 'icon_government',
    ),
]

DEFAULT_THEME = ([], 'default', '#4357C8', '#EEF2FF', '#6B7CE0', '#1A4FA0', 'icon_question')


# ──────────────────────────────────────────────
#  SVG-иконки: каждая — список SVG-элементов
#  cx, cy = центр круга (300, 322), r = 168
#  s = масштабный коэффициент
# ──────────────────────────────────────────────

def icon_contract(cx, cy, r, white, accent):
    s = r / 168
    return (
        f'<rect x="{cx-94*s}" y="{cy-76*s}" width="{104*s}" height="{140*s}" rx="{10*s}" fill="{white}"/>'
        f'<rect x="{cx-10*s}" y="{cy-90*s}" width="{104*s}" height="{140*s}" rx="{10*s}" fill="{white}" opacity=".9"/>'
        f'<line x1="{cx+6*s}" y1="{cy-64*s}" x2="{cx+78*s}" y2="{cy-64*s}" stroke="{accent}" stroke-width="{6*s}" stroke-linecap="round"/>'
        f'<line x1="{cx+6*s}" y1="{cy-44*s}" x2="{cx+78*s}" y2="{cy-44*s}" stroke="{accent}" stroke-width="{6*s}" stroke-linecap="round" opacity=".6"/>'
        f'<line x1="{cx+6*s}" y1="{cy-24*s}" x2="{cx+58*s}" y2="{cy-24*s}" stroke="{accent}" stroke-width="{6*s}" stroke-linecap="round" opacity=".4"/>'
        f'<path d="M{cx-78*s} {cy+80*s} L{cx-38*s} {cy+100*s} L{cx-4*s} {cy+92*s} '
        f'L{cx+22*s} {cy+104*s} L{cx+56*s} {cy+86*s}" stroke="{white}" stroke-width="{20*s}" '
        f'stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
    )


def icon_shield(cx, cy, r, white, accent):
    s = r / 168
    return (
        f'<path d="M{cx} {cy-108*s} L{cx+72*s} {cy-78*s} V{cy} '
        f'C{cx+72*s} {cy+46*s} {cx+40*s} {cy+76*s} {cx} {cy+100*s} '
        f'C{cx-40*s} {cy+76*s} {cx-72*s} {cy+46*s} {cx-72*s} {cy} V{cy-78*s} Z" fill="{white}"/>'
        f'<path d="M{cx-14*s} {cy-2*s} L{cx-2*s} {cy+14*s} L{cx+18*s} {cy-20*s}" '
        f'stroke="{accent}" stroke-width="{10*s}" stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
    )


def icon_fire(cx, cy, r, white, accent):
    s = r / 168
    return (
        f'<path d="M{cx} {cy+90*s} C{cx-80*s} {cy+30*s} {cx-60*s} {cy-50*s} {cx} {cy-90*s} '
        f'C{cx+60*s} {cy-50*s} {cx+80*s} {cy+30*s} {cx} {cy+90*s}Z" fill="{white}"/>'
        f'<path d="M{cx} {cy+60*s} C{cx-40*s} {cy+20*s} {cx-28*s} {cy-20*s} {cx} {cy-50*s} '
        f'C{cx+28*s} {cy-20*s} {cx+40*s} {cy+20*s} {cx} {cy+60*s}Z" fill="{accent}" opacity=".5"/>'
    )


def icon_sanitary(cx, cy, r, white, accent):
    s = r / 168
    return (
        f'<circle cx="{cx}" cy="{cy-22*s}" r="{78*s}" fill="{white}"/>'
        f'<path d="M{cx-38*s} {cy-10*s} C{cx-38*s} {cy-38*s} {cx+38*s} {cy-38*s} {cx+38*s} {cy-10*s} '
        f'C{cx+38*s} {cy+18*s} {cx} {cy+50*s} {cx} {cy+50*s} '
        f'C{cx} {cy+50*s} {cx-38*s} {cy+18*s} {cx-38*s} {cy-10*s} Z" fill="{accent}"/>'
        f'<circle cx="{cx}" cy="{cy-22*s}" r="{78*s}" stroke="{accent}" stroke-width="{12*s}" fill="none"/>'
        f'<rect x="{cx+46*s}" y="{cy+28*s}" width="{74*s}" height="{22*s}" rx="{11*s}" '
        f'transform="rotate(45 {cx+46*s} {cy+28*s})" fill="{white}" opacity=".7"/>'
    )


def icon_workplace(cx, cy, r, white, accent):
    s = r / 168
    return (
        f'<rect x="{cx-94*s}" y="{cy+50*s}" width="{200*s}" height="{18*s}" rx="{6*s}" fill="{white}"/>'
        f'<rect x="{cx-68*s}" y="{cy-34*s}" width="{116*s}" height="{74*s}" rx="{8*s}" fill="{white}"/>'
        f'<rect x="{cx-54*s}" y="{cy-22*s}" width="{88*s}" height="{50*s}" rx="{4*s}" fill="{accent}"/>'
        f'<rect x="{cx-20*s}" y="{cy+40*s}" width="{20*s}" height="{12*s}" fill="{white}"/>'
        f'<path d="M{cx-104*s} {cy+50*s} L{cx-104*s} {cy-70*s} L{cx-68*s} {cy-82*s}" '
        f'stroke="{white}" stroke-width="{12*s}" stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
        f'<circle cx="{cx-64*s}" cy="{cy-78*s}" r="{14*s}" fill="#FFE08A"/>'
    )


def icon_gears(cx, cy, r, white, accent):
    s = r / 168
    return (
        f'<circle cx="{cx-10*s}" cy="{cy-4*s}" r="{58*s}" fill="{white}"/>'
        f'<circle cx="{cx-10*s}" cy="{cy-4*s}" r="{22*s}" fill="{accent}"/>'
        f'<rect x="{cx-18*s}" y="{cy-78*s}" width="{16*s}" height="{28*s}" rx="{4*s}" fill="{accent}"/>'
        f'<rect x="{cx-18*s}" y="{cy+30*s}" width="{16*s}" height="{28*s}" rx="{4*s}" fill="{accent}"/>'
        f'<rect x="{cx-84*s}" y="{cy-12*s}" width="{28*s}" height="{16*s}" rx="{4*s}" fill="{accent}"/>'
        f'<rect x="{cx+38*s}" y="{cy-12*s}" width="{28*s}" height="{16*s}" rx="{4*s}" fill="{accent}"/>'
        f'<circle cx="{cx+72*s}" cy="{cy+70*s}" r="{40*s}" fill="{white}"/>'
        f'<circle cx="{cx+72*s}" cy="{cy+70*s}" r="{15*s}" fill="{accent}"/>'
    )


def icon_transport(cx, cy, r, white, accent):
    s = r / 168
    return (
        f'<rect x="{cx-100*s}" y="{cy-20*s}" width="{140*s}" height="{90*s}" rx="{10*s}" fill="{white}"/>'
        f'<path d="M{cx+40*s} {cy+20*s} L{cx+40*s} {cy-20*s} L{cx+100*s} {cy-20*s} '
        f'L{cx+110*s} {cy+10*s} L{cx+110*s} {cy+70*s} Z" fill="{white}"/>'
        f'<rect x="{cx+54*s}" y="{cy-12*s}" width="{44*s}" height="{34*s}" rx="{6*s}" fill="{accent}"/>'
        f'<circle cx="{cx-50*s}" cy="{cy+76*s}" r="{22*s}" fill="{white}"/>'
        f'<circle cx="{cx+78*s}" cy="{cy+76*s}" r="{22*s}" fill="{white}"/>'
    )


def icon_construction(cx, cy, r, white, accent):
    s = r / 168
    return (
        f'<rect x="{cx-80*s}" y="{cy-10*s}" width="{80*s}" height="{110*s}" rx="{6*s}" fill="{white}"/>'
        f'<rect x="{cx-68*s}" y="{cy+4*s}" width="{18*s}" height="{18*s}" rx="{3*s}" fill="{accent}"/>'
        f'<rect x="{cx-38*s}" y="{cy+4*s}" width="{18*s}" height="{18*s}" rx="{3*s}" fill="{accent}"/>'
        f'<rect x="{cx-68*s}" y="{cy+32*s}" width="{18*s}" height="{18*s}" rx="{3*s}" fill="{accent}"/>'
        f'<rect x="{cx-38*s}" y="{cy+32*s}" width="{18*s}" height="{18*s}" rx="{3*s}" fill="{accent}"/>'
        f'<line x1="{cx+20*s}" y1="{cy+100*s}" x2="{cx+20*s}" y2="{cy-100*s}" '
        f'stroke="{white}" stroke-width="{10*s}" stroke-linecap="round"/>'
        f'<line x1="{cx+20*s}" y1="{cy-100*s}" x2="{cx+90*s}" y2="{cy-100*s}" '
        f'stroke="{white}" stroke-width="{10*s}" stroke-linecap="round"/>'
    )


def icon_electrical(cx, cy, r, white, accent):
    s = r / 168
    return (
        f'<polygon points="{cx-10*s},{cy-100*s} {cx-50*s},{cy+10*s} {cx-4*s},{cy+10*s} '
        f'{cx+10*s},{cy+100*s} {cx+50*s},{cy-10*s} {cx+4*s},{cy-10*s}" fill="{white}"/>'
        f'<polygon points="{cx},{cy-60*s} {cx-28*s},{cy+6*s} {cx},{cy+6*s} '
        f'{cx+10*s},{cy+60*s} {cx+28*s},{cy-6*s} {cx},{cy-6*s}" fill="{accent}"/>'
    )


def icon_radiation(cx, cy, r, white, accent):
    s = r / 168
    parts = [f'<circle cx="{cx}" cy="{cy}" r="{80*s}" fill="{white}"/>']
    for i in range(3):
        a1 = (i * 120 - 90) * math.pi / 180
        a2 = (i * 120 - 30) * math.pi / 180
        x1 = cx + 78 * s * math.cos(a1)
        y1 = cy + 78 * s * math.sin(a1)
        x2 = cx + 78 * s * math.cos(a2)
        y2 = cy + 78 * s * math.sin(a2)
        parts.append(
            f'<path d="M{cx} {cy} L{x1} {y1} A{78*s} {78*s} 0 0 1 {x2} {y2} Z" fill="{accent}"/>'
        )
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{20*s}" fill="{white}"/>')
    return ''.join(parts)


def icon_laser(cx, cy, r, white, accent):
    s = r / 168
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{60*s}" fill="{white}"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{60*s}" stroke="{accent}" stroke-width="{8*s}" fill="none"/>'
        f'<line x1="{cx}" y1="{cy}" x2="{cx+100*s}" y2="{cy-60*s}" '
        f'stroke="{white}" stroke-width="{8*s}" stroke-linecap="round"/>'
        f'<line x1="{cx}" y1="{cy}" x2="{cx+100*s}" y2="{cy+30*s}" '
        f'stroke="{white}" stroke-width="{6*s}" stroke-linecap="round" opacity=".6"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{16*s}" fill="{accent}"/>'
    )


def icon_ppe(cx, cy, r, white, accent):
    s = r / 168
    return (
        f'<path d="M{cx-70*s} {cy+10*s} C{cx-70*s} {cy-60*s} {cx+70*s} {cy-60*s} {cx+70*s} {cy+10*s} Z" fill="{white}"/>'
        f'<path d="M{cx-90*s} {cy+10*s} Q{cx-90*s} {cy+30*s} {cx-40*s} {cy+30*s} '
        f'L{cx+40*s} {cy+30*s} Q{cx+90*s} {cy+30*s} {cx+90*s} {cy+10*s}" fill="{white}"/>'
        f'<path d="M{cx-50*s} {cy-10*s} C{cx-50*s} {cy-40*s} {cx+50*s} {cy-40*s} {cx+50*s} {cy-10*s}" '
        f'stroke="{accent}" stroke-width="{6*s}" fill="none"/>'
    )


def icon_inspection(cx, cy, r, white, accent):
    s = r / 168
    return (
        f'<circle cx="{cx-10*s}" cy="{cy-22*s}" r="{70*s}" fill="{white}"/>'
        f'<circle cx="{cx-10*s}" cy="{cy-22*s}" r="{70*s}" stroke="{accent}" stroke-width="{10*s}" fill="none"/>'
        f'<rect x="{cx+40*s}" y="{cy+28*s}" width="{74*s}" height="{20*s}" rx="{10*s}" '
        f'transform="rotate(45 {cx+40*s} {cy+28*s})" fill="{white}"/>'
        f'<rect x="{cx-44*s}" y="{cy-50*s}" width="{68*s}" height="{56*s}" rx="{6*s}" fill="{accent}" opacity=".3"/>'
    )


def icon_accident(cx, cy, r, white, accent):
    s = r / 168
    return (
        f'<polygon points="{cx},{cy-90*s} {cx+90*s},{cy+60*s} {cx-90*s},{cy+60*s}" fill="{white}"/>'
        f'<line x1="{cx}" y1="{cy-30*s}" x2="{cx}" y2="{cy+4*s}" '
        f'stroke="{accent}" stroke-width="{16*s}" stroke-linecap="round"/>'
        f'<circle cx="{cx}" cy="{cy+28*s}" r="{8*s}" fill="{accent}"/>'
    )


def icon_insurance(cx, cy, r, white, accent):
    s = r / 168
    return (
        f'<path d="M{cx-80*s} {cy+10*s} C{cx-80*s} {cy-50*s} {cx+80*s} {cy-50*s} {cx+80*s} {cy+10*s}" fill="{white}"/>'
        f'<line x1="{cx}" y1="{cy-10*s}" x2="{cx}" y2="{cy+90*s}" '
        f'stroke="{white}" stroke-width="{10*s}" stroke-linecap="round"/>'
        f'<path d="M{cx-80*s} {cy+10*s} C{cx-54*s} {cy+26*s} {cx-26*s} {cy-6*s} {cx} {cy+10*s} '
        f'C{cx+26*s} {cy+26*s} {cx+54*s} {cy-6*s} {cx+80*s} {cy+10*s}" fill="{white}"/>'
    )


def icon_emergency(cx, cy, r, white, accent):
    s = r / 168
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{40*s}" fill="{white}"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{40*s}" stroke="{accent}" stroke-width="{8*s}" fill="none"/>'
        f'<path d="M{cx+50*s} {cy-30*s} A{60*s} {60*s} 0 0 1 {cx+50*s} {cy+30*s}" '
        f'stroke="{white}" stroke-width="{12*s}" fill="none"/>'
        f'<path d="M{cx+70*s} {cy-50*s} A{80*s} {80*s} 0 0 1 {cx+70*s} {cy+50*s}" '
        f'stroke="{white}" stroke-width="{10*s}" fill="none" opacity=".6"/>'
        f'<line x1="{cx}" y1="{cy-20*s}" x2="{cx}" y2="{cy+20*s}" '
        f'stroke="{accent}" stroke-width="{10*s}" stroke-linecap="round"/>'
        f'<line x1="{cx-20*s}" y1="{cy}" x2="{cx+20*s}" y2="{cy}" '
        f'stroke="{accent}" stroke-width="{10*s}" stroke-linecap="round"/>'
    )


def icon_psychology(cx, cy, r, white, accent):
    s = r / 168
    return (
        f'<circle cx="{cx}" cy="{cy-20*s}" r="{52*s}" fill="{white}"/>'
        f'<path d="M{cx-36*s} {cy+18*s} C{cx-36*s} {cy+60*s} {cx+36*s} {cy+60*s} {cx+36*s} {cy+18*s}" fill="{white}"/>'
        f'<path d="M{cx-20*s} {cy-36*s} C{cx-20*s} {cy-56*s} {cx+20*s} {cy-56*s} {cx+20*s} {cy-36*s}" '
        f'stroke="{accent}" stroke-width="{6*s}" fill="none"/>'
        f'<line x1="{cx}" y1="{cy-56*s}" x2="{cx}" y2="{cy-36*s}" stroke="{accent}" stroke-width="{5*s}"/>'
    )


def icon_question(cx, cy, r, white, accent):
    s = r / 168
    return (
        f'<path d="M{cx-38*s} {cy-56*s} C{cx-38*s} {cy-86*s} {cx+22*s} {cy-86*s} {cx+22*s} {cy-56*s} '
        f'C{cx+22*s} {cy-38*s} {cx} {cy-24*s} {cx} {cy}" '
        f'stroke="{white}" stroke-width="{28*s}" stroke-linecap="round" fill="none"/>'
        f'<circle cx="{cx}" cy="{cy+60*s}" r="{18*s}" fill="{white}"/>'
    )


def icon_law(cx, cy, r, white, accent):
    """Весы правосудия (законодательство/нормативка)."""
    s = r / 168
    return (
        f'<line x1="{cx}" y1="{cy-80*s}" x2="{cx}" y2="{cy+70*s}" stroke="{white}" stroke-width="{10*s}" stroke-linecap="round"/>'
        f'<line x1="{cx-70*s}" y1="{cy-50*s}" x2="{cx+70*s}" y2="{cy-50*s}" stroke="{white}" stroke-width="{8*s}" stroke-linecap="round"/>'
        # left pan
        f'<path d="M{cx-70*s} {cy-50*s} L{cx-96*s} {cy-10*s} L{cx-44*s} {cy-10*s} Z" fill="{white}"/>'
        # right pan
        f'<path d="M{cx+70*s} {cy-50*s} L{cx+44*s} {cy-10*s} L{cx+96*s} {cy-10*s} Z" fill="{white}"/>'
        # base
        f'<rect x="{cx-30*s}" y="{cy+70*s}" width="{60*s}" height="{12*s}" rx="{4*s}" fill="{white}"/>'
    )


def icon_rights(cx, cy, r, white, accent):
    """Ладонь/защита прав."""
    s = r / 168
    return (
        f'<rect x="{cx-60*s}" y="{cy-70*s}" width="{120*s}" height="{140*s}" rx="{14*s}" fill="{white}"/>'
        f'<path d="M{cx-40*s} {cy-30*s} L{cx-40*s} {cy+40*s} Q{cx-40*s} {cy+55*s} {cx-25*s} {cy+55*s} '
        f'L{cx+30*s} {cy+55*s} Q{cx+45*s} {cy+55*s} {cx+45*s} {cy+40*s} L{cx+45*s} {cy} '
        f'Q{cx+45*s} {cy-12*s} {cx+33*s} {cy-12*s} L{cx+15*s} {cy-12*s} '
        f'L{cx+15*s} {cy-35*s} Q{cx+15*s} {cy-48*s} {cx+3*s} {cy-48*s} Q{cx-8*s} {cy-48*s} {cx-8*s} {cy-35*s} '
        f'L{cx-8*s} {cy-12*s} L{cx-30*s} {cy-12*s} L{cx-40*s} {cy-30*s} Z" fill="{accent}"/>'
    )


def icon_government(cx, cy, r, white, accent):
    """Здание с колоннами (госуправление)."""
    s = r / 168
    cols = 4
    col_w = 14 * s
    span = 130 * s
    half = 75 * s
    parts = [
        # pediment (triangle roof)
        f'<polygon points="{cx},{cy-90*s} {cx+half},{cy-50*s} {cx-half},{cy-50*s}" fill="{white}"/>',
        # base
        f'<rect x="{cx-80*s}" y="{cy+60*s}" width="{160*s}" height="{16*s}" rx="{4*s}" fill="{white}"/>',
        # architrave
        f'<rect x="{cx-80*s}" y="{cy-50*s}" width="{160*s}" height="{14*s}" fill="{white}"/>',
    ]
    for i in range(cols):
        x = cx - span/2 + i * (span/(cols-1)) - col_w/2
        parts.append(f'<rect x="{x:.1f}" y="{cy-36*s}" width="{col_w}" height="{96*s}" rx="{3*s}" fill="{white}"/>')
    return ''.join(parts)


# ──────────────────────────────────────────────
#  Ядро: детекция темы → сборка SVG
# ──────────────────────────────────────────────

ICON_FUNCS = {
    'icon_contract': icon_contract,
    'icon_shield': icon_shield,
    'icon_fire': icon_fire,
    'icon_sanitary': icon_sanitary,
    'icon_workplace': icon_workplace,
    'icon_gears': icon_gears,
    'icon_transport': icon_transport,
    'icon_construction': icon_construction,
    'icon_electrical': icon_electrical,
    'icon_radiation': icon_radiation,
    'icon_laser': icon_laser,
    'icon_ppe': icon_ppe,
    'icon_inspection': icon_inspection,
    'icon_accident': icon_accident,
    'icon_insurance': icon_insurance,
    'icon_emergency': icon_emergency,
    'icon_psychology': icon_psychology,
    'icon_question': icon_question,
    'icon_law': icon_law,
    'icon_rights': icon_rights,
    'icon_government': icon_government,
}


def detect_theme(text):
    """Определяет тему по ключевым словам. Возвращает кортеж."""
    text_lower = text.lower()
    best, best_count = DEFAULT_THEME, 0
    for theme in THEMES:
        count = sum(1 for kw in theme[0] if kw in text_lower)
        if count > best_count:
            best_count = count
            best = theme
    return best


def build_svg(title, theme_tuple=None):
    """Генерирует SVG-строку 1200×720."""
    if theme_tuple is None:
        theme_tuple = DEFAULT_THEME
    _, theme_key, accent, bg, line, dark, icon_func_name = theme_tuple
    icon_func = ICON_FUNCS.get(icon_func_name, icon_question)

    cx, cy, r = 300, 322, 168
    icon_svg = icon_func(cx, cy, r, '#FFFFFF', accent)

    title_w = min(len(title) * 8 + 60, 500)
    body_widths = [392, 336, 372, 264]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 720" fill="none">',
        f'  <rect width="1200" height="720" fill="{bg}"/>',
        f'  <circle cx="{cx}" cy="{cy}" r="{r}" fill="{accent}"/>',
        f'  {icon_svg}',
        f'  <rect x="586" y="184" width="{title_w}" height="64" rx="18" fill="{accent}"/>',
        f'  <line x1="610" y1="216" x2="{586 + title_w - 24}" y2="216" stroke="#FFFFFF" stroke-width="8" stroke-linecap="round"/>',
    ]
    for i, w in enumerate(body_widths):
        op = 1.0 - i * 0.15
        op_str = f' opacity="{op}"' if op < 1 else ''
        parts.append(f'  <rect x="586" y="{286 + i*42}" width="{w}" height="24" rx="12" fill="{line}"{op_str}/>')
    parts.append(f'  <rect x="586" y="478" width="196" height="66" rx="20" fill="{dark}"/>')
    parts.append('</svg>')
    return '\n'.join(parts)


def _image_file_exists(item):
    """True если у статьи есть image и файл реально лежит на диске."""
    if not item.image:
        return False
    return (Path(settings.MEDIA_ROOT) / item.image.name).exists()


def generate_for_item(item, overwrite=False):
    """Генерирует SVG и привязывает к ContentItem через image.

    По умолчанию пропускает статьи, у которых уже есть рабочая картинка.
    overwrite=True перезаписывает в т.ч. битые изображения (файл отсутствует).
    """
    if item.image and not overwrite:
        return False, 'has-image'
    if item.image and _image_file_exists(item) and not overwrite:
        return False, 'has-image'
    # Если image задан, но файла нет (битый путь) — перезапишем.
    text = f'{item.title} {item.excerpt or ""}'
    theme = detect_theme(text)
    svg_str = build_svg(item.display_title, theme)
    filename = f'qa-{item.id}-{item.slug[:60]}.svg'
    item.image.save(filename, ContentFile(svg_str.encode('utf-8')), save=True)
    return True, theme[1]


def assign_existing():
    """Привязать 5 ручных SVG к конкретным статьям."""
    mapping = {
        159: 'labour-contract.svg',
        229: 'ot-system.svg',
        245: 'sanitary-supervision.svg',
        365: 'workplace.svg',
        390: 'production-process.svg',
    }
    static_dir = Path(__file__).resolve().parent / 'static' / 'img' / 'generated' / 'qa'
    results = []
    for item_id, filename in mapping.items():
        item = ContentItem.objects.filter(id=item_id).first()
        if not item:
            results.append(('SKIP', f'id={item_id} не найдена'))
            continue
        src = static_dir / filename
        if not src.exists():
            results.append(('FAIL', f'{filename} не найден'))
            continue
        svg_bytes = src.read_bytes()
        item.image.save(filename, ContentFile(svg_bytes), save=True)
        results.append(('OK', f'id={item.id} → {item.image.name}  ({item.title[:60]})'))
    return results


def _collect_descendant_ids(cat_id):
    """Собирает id категории и всех её потомков рекурсивно."""
    ids = [cat_id]
    for child in Category.objects.filter(parent_id=cat_id):
        ids.extend(_collect_descendant_ids(child.id))
    return ids


def build_queryset(args):
    """Строит QuerySet по параметрам.

    По умолчанию возвращает статьи, которым нужна картинка:
    image пусто/None. Опция include_broken также включает статьи с битым путём
    (файла нет на диске). Рабочие картинки всегда исключаются.
    """
    qs = ContentItem.objects.select_related('category')
    if args.ids:
        qs = qs.filter(id__in=args.ids)
    elif args.cat:
        cat = Category.objects.filter(
            Q(slug=args.cat) | Q(public_slug=args.cat)
        ).first()
        if cat:
            qs = qs.filter(category_id__in=_collect_descendant_ids(cat.id))
    else:
        root = Category.objects.filter(public_slug='vopros-otvet').first()
        if root:
            qs = qs.filter(category_id__in=_collect_descendant_ids(root.id))

    # Пустые (нет image) — всегда кандидаты.
    empty_qs = qs.filter(image__isnull=True) | qs.filter(image='')

    if args.include_broken:
        # добавить статьи, где image задан, но файла нет на диске
        media = Path(settings.MEDIA_ROOT)
        broken_ids = []
        for it in qs.exclude(image__isnull=True).exclude(image=''):
            if not (media / it.image.name).exists():
                broken_ids.append(it.id)
        result = empty_qs | qs.filter(id__in=broken_ids)
    else:
        result = empty_qs

    return result.order_by('id')


# ──────────────────────────────────────────────
#  CLI entry point
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='SVG-генератор иллюстраций для статей')
    parser.add_argument('--all', action='store_true', help='Все статьи QA без картинок')
    parser.add_argument('--ids', nargs='+', type=int, help='Конкретные id статей')
    parser.add_argument('--cat', type=str, help='slug категории')
    parser.add_argument('--dry-run', action='store_true', help='Показать без записи')
    parser.add_argument('--assign-existing', action='store_true', help='Привязать 5 ручных SVG')
    parser.add_argument('--include-broken', action='store_true',
                        help='Также перезаписать битые картинки (файла нет на диске)')
    parser.add_argument('--limit', type=int, default=0, help='Лимит (0 = безлимит)')
    args = parser.parse_args()

    if args.assign_existing:
        print('Привязываю 5 ручных SVG из static/img/generated/qa/ к статьям...\n')
        for status, msg in assign_existing():
            prefix = '✓' if status == 'OK' else '✗' if status == 'FAIL' else '·'
            print(f'  {prefix} {msg}')
        print('\nГотово.')
        return

    qs = build_queryset(args)
    if not qs.exists():
        print('Нет подходящих статей.')
        return

    if args.dry_run:
        total = qs.count()
        label = 'без картинки (включая битые)' if args.include_broken else 'без картинки'
        print(f'Найдено {total} статей {label}:\n')
        for item in qs[:args.limit or 20]:
            theme = detect_theme(f'{item.title} {item.excerpt or ""}')
            broken_tag = ' [битая]' if (item.image and not _image_file_exists(item)) else ''
            print(f'  id={item.id:5d}  theme={theme[1]:20s}  {item.title[:70]}{broken_tag}')
        if total > (args.limit or 20):
            print(f'  ... и ещё {total - (args.limit or 20)}')
        return

    limit = args.limit or qs.count()
    generated = skipped = 0
    print(f'Генерирую SVG ({limit} шт.)...\n')
    for item in qs[:limit]:
        ok, info = generate_for_item(item, overwrite=args.include_broken)
        if ok:
            generated += 1
            print(f'  ✓ id={item.id} theme={info:20s} {item.title[:70]}')
        else:
            skipped += 1
    print(f'\nГотово. Сгенерировано {generated}, пропущено {skipped}.')


if __name__ == '__main__':
    main()
