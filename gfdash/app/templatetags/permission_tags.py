# app/templatetags/permission_tags.py

from django import template
from ..views.view_000global import has_permission

register = template.Library()

@register.filter
def is_allowed(user, template_name):
    """単一の画面に対する権限チェック"""
    return has_permission(user, template_name)

@register.filter
def is_any_allowed(user, template_names_str):
    """カンマ区切りの複数の画面のうち、1つでも権限があるかチェック"""
    template_names = [name.strip() for name in template_names_str.split(',')]
    for name in template_names:
        if has_permission(user, name):
            return True
    return False