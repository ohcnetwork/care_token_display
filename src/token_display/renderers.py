from rest_framework.renderers import TemplateHTMLRenderer


class TokenDisplayHTMLRenderer(TemplateHTMLRenderer):
    """
    Renders errors with the plugin's own template instead of the project's
    ``<status_code>.html``, so the display shows the actual reason a request failed.
    """

    exception_template_names = ["token_display/error.html"]
