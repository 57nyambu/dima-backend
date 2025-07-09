from django.views.generic import TemplateView

class DocumentationView(TemplateView):
    template_name = "docs/index.html"