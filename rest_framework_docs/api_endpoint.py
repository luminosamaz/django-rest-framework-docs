import json
import inspect
from django.contrib.admindocs.views import simplify_regex
from django.db.models.fields import NOT_PROVIDED
from django.utils.encoding import force_str

from rest_framework.fields import empty



class ApiEndpoint(object):

    def __init__(self, pattern, parent_pattern=None, drf_router=None):
        self.drf_router = drf_router
        self.pattern = pattern
        self.callback = pattern.callback
        # self.name = pattern.name
        self.docstring = self.__get_docstring__()
        self.name_parent = simplify_regex(parent_pattern.regex.pattern).strip('/') if parent_pattern else None
        self.path = self.__get_path__(parent_pattern)
        self.allowed_methods = self.__get_allowed_methods__()
        # self.view_name = pattern.callback.__name__
        self.errors = None
        self.fields = self.__get_serializer_fields__()
        self.fields_json = self.__get_serializer_fields_json__()
        self.permissions = self.__get_permissions_class__()

    def __get_path__(self, parent_pattern):
        if parent_pattern:
            return "/{0}{1}".format(self.name_parent, simplify_regex(self.pattern.regex.pattern))
        return simplify_regex(self.pattern.regex.pattern)

    def __get_allowed_methods__(self):
        viewset_methods = []
        if self.drf_router:
            for prefix, viewset, basename in self.drf_router.registry:
                if self.callback.cls != viewset:
                    continue

                lookup = self.drf_router.get_lookup_regex(viewset)
                routes = self.drf_router.get_routes(viewset)

                for route in routes:

                    # Only actions which actually exist on the viewset will be bound
                    mapping = self.drf_router.get_method_map(viewset, route.mapping)
                    if not mapping:
                        continue

                    # Build the url pattern
                    regex = route.url.format(
                        prefix=prefix,
                        lookup=lookup,
                        trailing_slash=self.drf_router.trailing_slash
                    )
                    if self.pattern.regex.pattern == regex:
                        funcs, viewset_methods = zip(
                            *[(mapping[m], m.upper()) for m in self.callback.cls.http_method_names if m in mapping]
                        )
                        viewset_methods = list(viewset_methods)
                        if len(set(funcs)) == 1:
                            self.docstring = inspect.getdoc(getattr(self.callback.cls, funcs[0]))

        view_methods = [force_str(m).upper() for m in self.callback.cls.http_method_names if hasattr(self.callback.cls, m)]
        return viewset_methods + view_methods

    def __get_docstring__(self):
        return inspect.getdoc(self.callback)

    def __get_permissions_class__(self):
        for perm_class in self.pattern.callback.cls.permission_classes:
            return perm_class.__name__

    def __get_serializer_fields__(self):
        def _default_str(field_name, field_default, model_fields):
            if field_default is not empty:
                return str(field_default)
            if model_fields is None:
                return None
            for model_field in model_fields:
                if model_field.name == field_name:
                    if hasattr(model_field, 'default'):
                        if model_field.default is not NOT_PROVIDED:
                            return str(model_field.default)
            return None

        fields = []
        serializer = None

        if hasattr(self.callback.cls, 'serializer_class'):
            serializer = self.callback.cls.serializer_class

        elif hasattr(self.callback.cls, 'get_serializer_class'):
            serializer = self.callback.cls.get_serializer_class(self.pattern.callback.cls())

        if hasattr(serializer, 'get_fields'):
            try:
                model_fields = None
                if hasattr(serializer, 'Meta'):
                    if hasattr(serializer.Meta, 'model'):
                        model_fields = serializer.Meta.model._meta.get_fields()

                fields = []
                for field_name, field in serializer().get_fields().items():
                    fields.append({
                        "name": field_name,
                        "type": str(field.__class__.__name__),
                        "read_only": field.read_only,
                        "default": _default_str(field_name, field.default,model_fields),
                        "required": field.required
                    })

            except KeyError as e:
                self.errors = e
                fields = []

            # FIXME:
            # Show more attibutes of `field`?

        return fields

    def __get_serializer_fields_json__(self):
        # FIXME:
        # Return JSON or not?
        return json.dumps(self.fields)
