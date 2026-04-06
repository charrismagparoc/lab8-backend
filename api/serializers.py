from rest_framework import serializers
from .models import SystemUser, Incident, Alert, EvacCenter, Resident, Resource, ActivityLog


class SystemUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemUser
        fields = '__all__'


class SystemUserPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemUser
        exclude = ['password']


class IncidentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Incident
        fields = '__all__'


class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = '__all__'


class EvacCenterSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvacCenter
        fields = '__all__'


class ResidentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resident
        fields = '__all__'


class ResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = '__all__'


class ActivityLogSerializer(serializers.ModelSerializer):
    userName = serializers.CharField(source='user_name', read_only=True)
    userRole = serializers.CharField(source='user_role', read_only=True)
    userStatus = serializers.CharField(source='user_status', read_only=True)

    class Meta:
        model = ActivityLog
        fields = '__all__'