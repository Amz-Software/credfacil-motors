import os
from django import template

register = template.Library()

@register.filter
def is_image_file(value):
    """
    Returns True if the file has an image extension.
    value should be a FieldFile or file object with a name attribute, or a string.
    """
    if not value:
        return False
        
    try:
        name = value.name
    except AttributeError:
        if isinstance(value, str):
            name = value
        else:
            return False
            
    if not name:
        return False
        
    ext = os.path.splitext(name)[1].lower()
    return ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg']
