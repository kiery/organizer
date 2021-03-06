# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging
from django.shortcuts import render
from django.conf import settings
from django.template import loader, engines
from django.core.mail import EmailMessage
from . import models
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import detail_route, list_route
from rest_framework.permissions import IsAuthenticatedOrReadOnly, AllowAny
from django.views.decorators.clickjacking import xframe_options_exempt
from . import serializers
from django.contrib.auth.models import User

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = serializers.UserSerializer

    def get_object(self):
        pk = self.kwargs.get('pk')

        if pk == 'me':
            return self.request.user

        return super(UserViewSet, self).get_object()

class ActivistViewSet(viewsets.ModelViewSet):
    queryset = models.Activist.objects.all()
    serializer_class = serializers.ActivistSerializer

    @list_route(methods=['get'])
    def recent(self, request):
        recent_activists = models.Activist.objects.all().order_by('-created')[0:10]
        page = self.paginate_queryset(recent_activists)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(recent_activists, many=True)
        return Response(serializer.data)

class SignupViewSet(viewsets.ModelViewSet):
    queryset = models.Signup.objects.all()
    serializer_class = serializers.SignupSerializer

class ActionViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticatedOrReadOnly,)
    queryset = models.Action.objects.all()
    serializer_class = serializers.ActionSerializer

    @detail_route(methods=['post'])
    def email_activists_preview(self, request, pk=None):
        action_obj = self.get_object()
        serializer = serializers.EmailSerializer(data={
            'subject': request.data.get('subject', None),
            'body': request.data.get('body', None),
            'signups': request.data.get('signups', None)
        })
        if serializer.is_valid():
            templated_body = engines['django'].from_string(serializer.validated_data.get('body'))
            email_template = loader.get_template('email.eml')
            signups = models.Signup.objects.filter(
                action=action_obj,
                pk__in=serializer.validated_data.get('signups')
            )
            s = signups[0]
            cxt = {
                'action': action_obj,
                'signup': s,
                'activist': s.activist
            }
            generated_email = email_template.render({
                'signup': s,
                'body': templated_body.render(cxt)
            })
            return Response({'body': generated_email})
        else:
            return Response({'errors': serializer.errors}, 400)

    @detail_route(methods=['post'])
    def email_activists(self, request, pk=None):
        action_obj = self.get_object()
        serializer = serializers.EmailSerializer(data={
            'subject': request.data.get('subject', None),
            'body': request.data.get('body', None),
            'signups': request.data.get('signups', None)
        })
        if serializer.is_valid():
            templated_body = engines['django'].from_string(serializer.validated_data.get('body'))
            email_template = loader.get_template('email.eml')
            signups = models.Signup.objects.filter(
                action=action_obj,
                pk__in=serializer.validated_data.get('signups')
            )
            for s in signups:
                cxt = {
                    'action': action_obj,
                    'signup': s,
                    'activist': s.activist
                }
                generated_email = email_template.render({
                    'signup': s,
                    'body': templated_body.render(cxt)
                })
                email_obj = EmailMessage(
                    subject=serializer.validated_data.get('subject'),
                    body=generated_email,
                    to=[s.activist.email],
                    reply_to=[request.user.email],
                )
                email_obj.encoding = 'utf-8'
                email_obj.send()
            return Response({'body': generated_email})
        else:
            return Response({'errors': serializer.errors}, 400)

class FormViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticatedOrReadOnly,)
    queryset = models.Form.objects.all()
    serializer_class = serializers.FormSerializer

    @detail_route(methods=['get'], permission_classes=(AllowAny,))
    def embed(self, request, pk=None):
        form_obj = self.get_object()
        embed_data = {
            'version': '1.0',
            'type': 'rich',
            'width': 400,
            'height': 500,
            'html': "<iframe src=\"https://organizing.eastbayforward.org/crm/f/%s\" width=400 height=500></iframe>"%(form_obj.id)
        }
        return Response(embed_data)

    @detail_route(methods=['post'], permission_classes=(AllowAny,))
    def submit_response(self, request, pk=None):
        form_obj = self.get_object()
        fields = models.FormField.objects.filter(form=form_obj).all()
        serializer = serializers.ResponseSerializer(data={
            'email': request.data['email'],
            'name': request.data.get('name', None),
            'address': request.data.get('address', None)
        })
        if serializer.is_valid():
            signup_activist, _ = models.Activist.objects.get_or_create(
                    email = request.data['email'],
                    defaults = {
                        'name': request.data.get('name', None),
                        'address': request.data.get('address', '')
                    })
            signup, _ = models.Signup.objects.update_or_create(
                    activist=signup_activist,
                    action=form_obj.action,
                    defaults={'state': form_obj.next_state})
            logging.debug("Updating signup: %s", signup )
            values = []
            for field in fields:
                field_input_name = "input_%s"%(field.id)
                field_value = request.data.get(field_input_name, '')
                logging.debug("%s = %s", field.name, field_value)
                models.FormResponse.objects.update_or_create(
                        field = field,
                        activist = signup_activist,
                        defaults = {'value': field_value})
            return Response()
        else:
            return Response({'errors': serializer.errors}, 400)

class FieldViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticatedOrReadOnly,)
    queryset = models.FormField.objects.all()
    serializer_class = serializers.FieldSerializer

class CampaignViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticatedOrReadOnly,)
    queryset = models.Campaign.objects.all()
    serializer_class = serializers.CampaignSerializer

def index(request, *args, **kwargs):
    return render(request, 'index.html', {'settings':settings})

@xframe_options_exempt
def view_form(request, form_id):
    form = models.Form.objects.get(pk=form_id)
    return render(request, 'form.html', {'form_obj': form, 'settings': settings})
