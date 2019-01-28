from __future__ import absolute_import, unicode_literals

from django.conf import settings
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.http import HttpResponseRedirect
from django.utils.encoding import force_text
from django.utils.translation import ugettext_lazy as _
from django.views.generic import DetailView
from django.views.generic import FormView as DjangoFormView
from django.views.generic import TemplateView
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.edit import (
    CreateView, DeleteView, FormMixin, ModelFormMixin, UpdateView
)
from django.views.generic.list import ListView

from django_downloadview import (
    TextIteratorIO, VirtualDownloadView, VirtualFile
)
from pure_pagination.mixins import PaginationMixin

from .forms import ChoiceForm
from .icons import (
    icon_assign_remove_add, icon_assign_remove_remove, icon_sort_down,
    icon_sort_up
)
from .literals import (
    TEXT_SORT_FIELD_PARAMETER, TEXT_SORT_FIELD_VARIABLE_NAME,
    TEXT_SORT_ORDER_CHOICE_ASCENDING, TEXT_SORT_ORDER_PARAMETER,
    TEXT_SORT_ORDER_VARIABLE_NAME
)
from .mixins import (
    DeleteExtraDataMixin, DynamicFormViewMixin, ExtraContextMixin,
    FormExtraKwargsMixin, ListModeMixin, MultipleObjectMixin,
    ObjectActionMixin, ObjectNameMixin, RedirectionMixin,
    RestrictedQuerysetMixin, ViewPermissionCheckMixin
)
from .settings import setting_paginate_by

__all__ = (
    'AssignRemoveView', 'ConfirmView', 'FormView',
    'MultiFormView', 'MultipleObjectConfirmActionView',
    'MultipleObjectFormActionView', 'MultipleObjectDownloadView',
    'SingleObjectCreateView', 'SingleObjectDeleteView',
    'SingleObjectDetailView', 'MultipleObjectDownloadView',
    'SingleObjectEditView', 'SingleObjectListView', 'SimpleView'
)


class AssignRemoveView(ExtraContextMixin, ViewPermissionCheckMixin, RestrictedQuerysetMixin, TemplateView):
    decode_content_type = False
    left_list_help_text = _(
        'Select entries to be added. Hold Control to select multiple '
        'entries. Once the selection is complete, click the button below '
        'or double click the list to activate the action.'
    )
    right_list_help_text = _(
        'Select entries to be removed. Hold Control to select multiple '
        'entries. Once the selection is complete, click the button below '
        'or double click the list to activate the action.'
    )
    grouped = False
    left_list_title = None
    right_list_title = None
    template_name = 'appearance/generic_form.html'

    LEFT_LIST_NAME = 'left_list'
    RIGHT_LIST_NAME = 'right_list'

    @staticmethod
    def generate_choices(choices):
        results = []
        for choice in choices:
            ct = ContentType.objects.get_for_model(model=choice)
            label = force_text(choice)

            results.append(('%s,%s' % (ct.model, choice.pk), '%s' % (label)))

        # Sort results by the label not the key value
        return sorted(results, key=lambda x: x[1])

    def left_list(self):
        # Subclass must override
        raise NotImplementedError

    def right_list(self):
        # Subclass must override
        raise NotImplementedError

    def add(self, item):
        # Subclass must override
        raise NotImplementedError

    def remove(self, item):
        # Subclass must override
        raise NotImplementedError

    def get_disabled_choices(self):
        return ()

    def get_left_list_help_text(self):
        return self.left_list_help_text

    def get_right_list_help_text(self):
        return self.right_list_help_text

    def get(self, request, *args, **kwargs):
        self.unselected_list = ChoiceForm(
            choices=self.left_list(), help_text=self.get_left_list_help_text(),
            prefix=self.LEFT_LIST_NAME
        )
        self.selected_list = ChoiceForm(
            choices=self.right_list(),
            disabled_choices=self.get_disabled_choices(),
            help_text=self.get_right_list_help_text(),
            prefix=self.RIGHT_LIST_NAME
        )
        return self.render_to_response(self.get_context_data())

    def process_form(self, prefix, items_function, action_function):
        if '%s-submit' % prefix in self.request.POST.keys():
            form = ChoiceForm(
                self.request.POST, choices=items_function(), prefix=prefix
            )

            if form.is_valid():
                for selection in form.cleaned_data['selection']:
                    if self.grouped:
                        flat_list = []
                        for group in items_function():
                            flat_list.extend(group[1])
                    else:
                        flat_list = items_function()

                    label = dict(flat_list)[selection]
                    if self.decode_content_type:
                        model, pk = selection.split(',')
                        selection_obj = ContentType.objects.get(
                            model=model
                        ).get_object_for_this_type(pk=pk)
                    else:
                        selection_obj = selection

                    try:
                        action_function(selection_obj)
                    except Exception:
                        if settings.DEBUG:
                            raise
                        else:
                            messages.error(
                                self.request,
                                _('Unable to transfer selection: %s.') % label
                            )

    def post(self, request, *args, **kwargs):
        self.process_form(
            action_function=self.add, items_function=self.left_list,
            prefix=self.LEFT_LIST_NAME
        )
        self.process_form(
            action_function=self.remove, items_function=self.right_list,
            prefix=self.RIGHT_LIST_NAME
        )
        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        data = super(AssignRemoveView, self).get_context_data(**kwargs)
        data.update(
            {
                'subtemplates_list': [
                    {
                        'name': 'appearance/generic_form_subtemplate.html',
                        'column_class': 'col-xs-12 col-sm-6 col-md-6 col-lg-6',
                        'context': {
                            'form': self.unselected_list,
                            'form_css_classes': 'form-hotkey-double-click',
                            'title': self.left_list_title or ' ',
                            'submit_label': _('Add'),
                            'submit_icon_class': icon_assign_remove_add,
                            'hide_labels': True,
                        }
                    },
                    {
                        'name': 'appearance/generic_form_subtemplate.html',
                        'column_class': 'col-xs-12 col-sm-6 col-md-6 col-lg-6',
                        'context': {
                            'form': self.selected_list,
                            'form_css_classes': 'form-hotkey-double-click',
                            'title': self.right_list_title or ' ',
                            'submit_label': _('Remove'),
                            'submit_icon_class': icon_assign_remove_remove,
                            'hide_labels': True,
                        }
                    },
                ],
            }
        )
        return data


class ConfirmView(RestrictedQuerysetMixin, ViewPermissionCheckMixin, ExtraContextMixin, RedirectionMixin, TemplateView):
    template_name = 'appearance/generic_confirm.html'

    def post(self, request, *args, **kwargs):
        self.view_action()
        return HttpResponseRedirect(redirect_to=self.get_success_url())


class FormView(ViewPermissionCheckMixin, ExtraContextMixin, RedirectionMixin, FormExtraKwargsMixin, DjangoFormView):
    template_name = 'appearance/generic_form.html'


class DynamicFormView(DynamicFormViewMixin, FormView):
    pass


class DownloadViewBase(VirtualDownloadView):
    TextIteratorIO = TextIteratorIO
    VirtualFile = VirtualFile


class MultipleObjectDownloadView(RestrictedQuerysetMixin, MultipleObjectMixin, DownloadViewBase):
    """
    View that support receiving multiple objects via a pk_list query.
    """
    def __init__(self, *args, **kwargs):
        result = super(MultipleObjectDownloadView, self).__init__(*args, **kwargs)

        if self.__class__.mro()[0].get_queryset != MultipleObjectDownloadView.get_queryset:
            raise ImproperlyConfigured(
                '%(cls)s is overloading the get_queryset method. Subclasses '
                'should implement the get_source_queryset method instead. ' % {
                    'cls': self.__class__.__name__
                }
            )

        return result

    def get_queryset(self):
        try:
            return super(MultipleObjectDownloadView, self).get_queryset()
        except ImproperlyConfigured:
            self.queryset = self.get_source_queryset()
            return super(MultipleObjectDownloadView, self).get_queryset()


class SingleObjectDownloadView(RestrictedQuerysetMixin, SingleObjectMixin, DownloadViewBase):
    """
    View that provides a .get_object() method to download content from a
    single object.
    """
    def __init__(self, *args, **kwargs):
        result = super(SingleObjectDownloadView, self).__init__(*args, **kwargs)

        if self.__class__.mro()[0].get_queryset != SingleObjectDownloadView.get_queryset:
            raise ImproperlyConfigured(
                '%(cls)s is overloading the get_queryset method. Subclasses '
                'should implement the get_source_queryset method instead. ' % {
                    'cls': self.__class__.__name__
                }
            )

        return result

    def get_queryset(self):
        try:
            return super(SingleObjectDownloadView, self).get_queryset()
        except ImproperlyConfigured:
            self.queryset = self.get_source_queryset()
            return super(SingleObjectDownloadView, self).get_queryset()


class MultiFormView(DjangoFormView):
    prefix = None
    prefixes = {}

    def _create_form(self, form_name, klass):
        form_kwargs = self.get_form_kwargs(form_name)
        form_create_method = 'create_%s_form' % form_name
        if hasattr(self, form_create_method):
            form = getattr(self, form_create_method)(**form_kwargs)
        else:
            form = klass(**form_kwargs)
        return form

    def forms_valid(self, forms):
        for form_name, form in forms.items():
            form_valid_method = '%s_form_valid' % form_name

            if hasattr(self, form_valid_method):
                return getattr(self, form_valid_method)(form)

        self.all_forms_valid(forms)

        return HttpResponseRedirect(redirect_to=self.get_success_url())

    def forms_invalid(self, forms):
        return self.render_to_response(self.get_context_data(forms=forms))

    def get(self, request, *args, **kwargs):
        form_classes = self.get_form_classes()
        forms = self.get_forms(form_classes)
        return self.render_to_response(self.get_context_data(forms=forms))

    def get_context_data(self, **kwargs):
        """
        Insert the form into the context dict.
        """
        if 'forms' not in kwargs:
            kwargs['forms'] = self.get_forms(
                form_classes=self.get_form_classes()
            )
        return super(FormMixin, self).get_context_data(**kwargs)

    def get_form_classes(self):
        return self.form_classes

    def get_form_kwargs(self, form_name):
        kwargs = {}
        kwargs.update({'initial': self.get_initial(form_name)})
        kwargs.update({'prefix': self.get_prefix(form_name)})

        if self.request.method in ('POST', 'PUT'):
            kwargs.update({
                'data': self.request.POST,
                'files': self.request.FILES,
            })

        return kwargs

    def get_forms(self, form_classes):
        return dict(
            [
                (
                    key, self._create_form(key, klass)
                ) for key, klass in form_classes.items()
            ]
        )

    def get_initial(self, form_name):
        initial_method = 'get_%s_initial' % form_name
        if hasattr(self, initial_method):
            return getattr(self, initial_method)()
        else:
            return self.initial.copy()

    def get_prefix(self, form_name):
        return self.prefixes.get(form_name, self.prefix)

    def post(self, request, *args, **kwargs):
        form_classes = self.get_form_classes()
        forms = self.get_forms(form_classes)

        if all([form.is_valid() for form in forms.values()]):
            return self.forms_valid(forms=forms)
        else:
            return self.forms_invalid(forms=forms)


class MultipleObjectFormActionView(ObjectActionMixin, ViewPermissionCheckMixin, RestrictedQuerysetMixin, MultipleObjectMixin, FormExtraKwargsMixin, ExtraContextMixin, RedirectionMixin, DjangoFormView):
    """
    This view will present a form and upon receiving a POST request will
    perform an action on an object or queryset
    """
    template_name = 'appearance/generic_form.html'

    def __init__(self, *args, **kwargs):
        result = super(MultipleObjectFormActionView, self).__init__(*args, **kwargs)

        if self.__class__.mro()[0].get_queryset != MultipleObjectFormActionView.get_queryset:
            raise ImproperlyConfigured(
                '%(cls)s is overloading the get_queryset method. Subclasses '
                'should implement the get_source_queryset method instead. ' % {
                    'cls': self.__class__.__name__
                }
            )

        return result

    def form_valid(self, form):
        self.view_action(form=form)
        return super(MultipleObjectFormActionView, self).form_valid(form=form)

    def get_queryset(self):
        try:
            return super(MultipleObjectFormActionView, self).get_queryset()
        except ImproperlyConfigured:
            self.queryset = self.get_source_queryset()
            return super(MultipleObjectFormActionView, self).get_queryset()


class MultipleObjectConfirmActionView(ObjectActionMixin, ViewPermissionCheckMixin, RestrictedQuerysetMixin, MultipleObjectMixin, ExtraContextMixin, RedirectionMixin, TemplateView):
    template_name = 'appearance/generic_confirm.html'

    def __init__(self, *args, **kwargs):
        result = super(MultipleObjectConfirmActionView, self).__init__(*args, **kwargs)

        if self.__class__.mro()[0].get_queryset != MultipleObjectConfirmActionView.get_queryset:
            raise ImproperlyConfigured(
                '%(cls)s is overloading the get_queryset method. Subclasses '
                'should implement the get_source_queryset method instead. ' % {
                    'cls': self.__class__.__name__
                }
            )

        return result

    def get_queryset(self):
        try:
            return super(MultipleObjectConfirmActionView, self).get_queryset()
        except ImproperlyConfigured:
            self.queryset = self.get_source_queryset()
            return super(MultipleObjectConfirmActionView, self).get_queryset()

    def post(self, request, *args, **kwargs):
        self.view_action()
        return HttpResponseRedirect(redirect_to=self.get_success_url())


class SimpleView(ViewPermissionCheckMixin, ExtraContextMixin, TemplateView):
    pass


class SingleObjectCreateView(ObjectNameMixin, ViewPermissionCheckMixin, ExtraContextMixin, RedirectionMixin, FormExtraKwargsMixin, CreateView):
    template_name = 'appearance/generic_form.html'
    error_message_duplicate = None

    def form_valid(self, form):
        # This overrides the original Django form_valid method

        self.object = form.save(commit=False)

        if hasattr(self, 'get_instance_extra_data'):
            for key, value in self.get_instance_extra_data().items():
                setattr(self.object, key, value)

        if hasattr(self, 'get_save_extra_data'):
            save_extra_data = self.get_save_extra_data()
        else:
            save_extra_data = {}

        try:
            self.object.validate_unique()
        except ValidationError as exception:
            context = self.get_context_data()

            error_message = self.get_error_message_duplicate() or _(
                'Duplicate data error: %(error)s'
            ) % {
                'error': '\n'.join(exception.messages)
            }

            messages.error(
                message=error_message, request=self.request
            )
            return super(
                SingleObjectCreateView, self
            ).form_invalid(form=form)

        try:
            self.object.save(**save_extra_data)
        except Exception as exception:
            context = self.get_context_data()

            messages.error(
                self.request,
                _('%(object)s not created, error: %(error)s') % {
                    'object': self.get_object_name(context=context),
                    'error': exception
                }
            )
            return super(
                SingleObjectCreateView, self
            ).form_invalid(form=form)
        else:
            context = self.get_context_data()

            messages.success(
                message=_(
                    '%(object)s created successfully.'
                ) % {'object': self.get_object_name(context=context)},
                request=self.request
            )

        return HttpResponseRedirect(redirect_to=self.get_success_url())

    def get_error_message_duplicate(self):
        return self.error_message_duplicate


class SingleObjectDynamicFormCreateView(DynamicFormViewMixin, SingleObjectCreateView):
    pass


class SingleObjectDeleteView(ObjectNameMixin, DeleteExtraDataMixin, ViewPermissionCheckMixin, RestrictedQuerysetMixin, ExtraContextMixin, RedirectionMixin, DeleteView):
    template_name = 'appearance/generic_confirm.html'

    def __init__(self, *args, **kwargs):
        result = super(SingleObjectDeleteView, self).__init__(*args, **kwargs)

        if self.__class__.mro()[0].get_queryset != SingleObjectDeleteView.get_queryset:
            raise ImproperlyConfigured(
                '%(cls)s is overloading the get_queryset method. Subclasses '
                'should implement the get_source_queryset method instead. ' % {
                    'cls': self.__class__.__name__
                }
            )

        return result

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data()
        object_name = self.get_object_name(context=context)

        try:
            result = super(SingleObjectDeleteView, self).delete(request, *args, **kwargs)
        except Exception as exception:
            messages.error(
                message=_('%(object)s not deleted, error: %(error)s.') % {
                    'object': object_name,
                    'error': exception
                }, request=self.request
            )

            raise exception
        else:
            messages.success(
                message=_(
                    '%(object)s deleted successfully.'
                ) % {'object': object_name},
                request=self.request
            )

            return result

    def get_context_data(self, **kwargs):
        context = super(SingleObjectDeleteView, self).get_context_data(**kwargs)
        context.update({'delete_view': True})
        return context

    def get_queryset(self):
        try:
            return super(SingleObjectDeleteView, self).get_queryset()
        except ImproperlyConfigured:
            self.queryset = self.get_source_queryset()
            return super(SingleObjectDeleteView, self).get_queryset()


class SingleObjectDetailView(ViewPermissionCheckMixin, RestrictedQuerysetMixin, FormExtraKwargsMixin, ExtraContextMixin, ModelFormMixin, DetailView):
    template_name = 'appearance/generic_form.html'

    def __init__(self, *args, **kwargs):
        result = super(SingleObjectDetailView, self).__init__(*args, **kwargs)

        if self.__class__.mro()[0].get_queryset != SingleObjectDetailView.get_queryset:
            raise ImproperlyConfigured(
                '%(cls)s is overloading the get_queryset method. Subclasses '
                'should implement the get_source_queryset method instead. ' % {
                    'cls': self.__class__.__name__
                }
            )

        return result

    def get_context_data(self, **kwargs):
        context = super(SingleObjectDetailView, self).get_context_data(**kwargs)
        context.update({'read_only': True, 'form': self.get_form()})
        return context

    def get_queryset(self):
        try:
            return super(SingleObjectDetailView, self).get_queryset()
        except ImproperlyConfigured:
            self.queryset = self.get_source_queryset()
            return super(SingleObjectDetailView, self).get_queryset()


class SingleObjectEditView(ObjectNameMixin, ViewPermissionCheckMixin, RestrictedQuerysetMixin, ExtraContextMixin, FormExtraKwargsMixin, RedirectionMixin, UpdateView):
    template_name = 'appearance/generic_form.html'

    def form_valid(self, form):
        # This overrides the original Django form_valid method

        self.object = form.save(commit=False)

        if hasattr(self, 'get_instance_extra_data'):
            for key, value in self.get_instance_extra_data().items():
                setattr(self.object, key, value)

        if hasattr(self, 'get_save_extra_data'):
            save_extra_data = self.get_save_extra_data()
        else:
            save_extra_data = {}

        context = self.get_context_data()
        object_name = self.get_object_name(context=context)

        try:
            self.object.save(**save_extra_data)
        except Exception as exception:
            messages.error(
                message=_('%(object)s not updated, error: %(error)s.') % {
                    'object': object_name,
                    'error': exception
                }, request=self.request
            )
            return super(
                SingleObjectEditView, self
            ).form_invalid(form=form)
        else:
            messages.success(
                message=_(
                    '%(object)s updated successfully.'
                ) % {'object': object_name}, request=self.request
            )

        return HttpResponseRedirect(redirect_to=self.get_success_url())

    def get_object(self, queryset=None):
        obj = super(SingleObjectEditView, self).get_object(queryset=queryset)

        if hasattr(self, 'get_instance_extra_data'):
            for key, value in self.get_instance_extra_data().items():
                setattr(obj, key, value)

        return obj


class SingleObjectDynamicFormEditView(DynamicFormViewMixin, SingleObjectEditView):
    pass


class SingleObjectListView(ListModeMixin, PaginationMixin, ViewPermissionCheckMixin, RestrictedQuerysetMixin, ExtraContextMixin, RedirectionMixin, ListView):
    template_name = 'appearance/generic_list.html'

    def __init__(self, *args, **kwargs):
        result = super(SingleObjectListView, self).__init__(*args, **kwargs)

        if self.__class__.mro()[0].get_queryset != SingleObjectListView.get_queryset:
            raise ImproperlyConfigured(
                '%(cls)s is overloading the get_queryset method. Subclasses '
                'should implement the get_source_queryset method instead. ' % {
                    'cls': self.__class__.__name__
                }
            )

        return result

    def get_context_data(self, **kwargs):
        context = super(SingleObjectListView, self).get_context_data(**kwargs)

        context.update(
            {
                TEXT_SORT_FIELD_VARIABLE_NAME: self.get_sort_field(),
                TEXT_SORT_ORDER_VARIABLE_NAME: self.get_sort_order(),
                'icon_sort': self.get_sort_icon(),
            }
        )
        return context

    def get_sort_field(self):
        return self.request.GET.get(TEXT_SORT_FIELD_PARAMETER)

    def get_sort_icon(self):
        sort_order = self.get_sort_order()
        if not sort_order:
            return
        elif sort_order == TEXT_SORT_ORDER_CHOICE_ASCENDING:
            return icon_sort_down
        else:
            return icon_sort_up

    def get_sort_order(self):
        return self.request.GET.get(TEXT_SORT_ORDER_PARAMETER)

    def get_paginate_by(self, queryset):
        return setting_paginate_by.value

    def get_queryset(self):
        try:
            queryset = super(SingleObjectListView, self).get_queryset()
        except ImproperlyConfigured:
            self.queryset = self.get_source_queryset()
            queryset = super(SingleObjectListView, self).get_queryset()

        self.field_name = self.get_sort_field()
        if self.get_sort_order() == TEXT_SORT_ORDER_CHOICE_ASCENDING:
            sort_order = ''
        else:
            sort_order = '-'

        if self.field_name:
            queryset = queryset.order_by(
                '{}{}'.format(sort_order, self.field_name)
            )

        return queryset
