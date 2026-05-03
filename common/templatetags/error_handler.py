# common/templatetags/error_handlers.py
from django import template
register = template.Library()

@register.tag
def try_block(parser, token):
    nodelist = parser.parse(('except', 'endtry'))
    parser.delete_first_token()
    except_nodelist = parser.parse(('endtry',))
    parser.delete_first_token()
    return TryNode(nodelist, except_nodelist)

class TryNode(template.Node):
    def __init__(self, nodelist, except_nodelist):
        self.nodelist = nodelist
        self.except_nodelist = except_nodelist
    def render(self, context):
        try:
            return self.nodelist.render(context)
        except:
            return self.except_nodelist.render(context)