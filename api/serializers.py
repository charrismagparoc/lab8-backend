from rest_framework import serializers
from .models import SystemUser, Incident, Alert, EvacCenter, Resident, Resource, ActivityLog


class SystemUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemUser
        fields = '__all__'


class SystemUserPublicSerializer(serializers.ModelSerializer):
    """Without password for listing"""
    class Meta:
        model = SystemUser
        exclude = ['password']


class IncidentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Incident
        fields = '__all__'
        read_only_fields = ['id', 'date_reported', 'created_at']


class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = '__all__'
        read_only_fields = ['id', 'sent_at', 'created_at']


class EvacCenterSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvacCenter
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class ResidentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resident
        fields = '__all__'
        read_only_fields = ['id', 'added_at', 'updated_at']


class ResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class ActivityLogSerializer(serializers.ModelSerializer):
    userName = serializers.CharField(source='user_name', read_only=True)

    class Meta:
        model = ActivityLog
        fields = '__all__'
        read_only_fields = ['id', 'created_at']