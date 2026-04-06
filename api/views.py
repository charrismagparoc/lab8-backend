from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import ActivityLog, Alert, EvacCenter, Incident, Resident, Resource, SystemUser
from .serializers import (
    ActivityLogSerializer, AlertSerializer, EvacCenterSerializer,
    IncidentSerializer, ResidentSerializer, ResourceSerializer,
    SystemUserPublicSerializer, SystemUserSerializer,
)


def log_action(action, log_type, user_name='System', urgent=False, user_role='System', user_status=''):
    ActivityLog.objects.create(
        action=action,
        type=log_type,
        user_name=user_name,
        user_role=user_role,
        user_status=user_status,
        urgent=urgent
    )


# ─── AUTH ──────────────────────────────────────────────────────────────────────

@api_view(['POST'])
def auth_login(request):
    email = request.data.get('email', '').strip().lower()
    password = request.data.get('password', '')

    if not email or not password:
        return Response({'ok': False, 'msg': 'Email and password required.'}, status=400)

    try:
        user = SystemUser.objects.get(email__iexact=email)
    except SystemUser.DoesNotExist:
        return Response({'ok': False, 'msg': 'Invalid credentials.'}, status=401)

    if user.password != password:
        return Response({'ok': False, 'msg': 'Invalid credentials.'}, status=401)

    # Block login only if Admin manually set the account inactive
    if user.role != 'Admin' and user.status == 'Inactive' and not user.is_online:
        # Allow login — status will be corrected below
        pass

    user.last_login = timezone.now()
    user.last_seen  = timezone.now()
    user.is_online  = True

    # Auto-set status on login
    if user.role != 'Admin':
        user.status = 'Active'
    else:
        user.status = 'Active'  # Admin always Active

    user.save(update_fields=['last_login', 'last_seen', 'is_online', 'status'])

    log_action(
        f'Signed in: {user.name} ({user.role})',
        'Auth',
        user.name,
        False,
        user.role,
        'Active'
    )

    return Response({
        'ok': True,
        'user': {
            'id':     str(user.id),
            'name':   user.name,
            'email':  user.email,
            'role':   user.role,
            'status': user.status,
        }
    })


@api_view(['POST'])
def auth_logout(request):
    user_name = request.data.get('user_name', 'Unknown User')
    user_id   = request.data.get('user_id')
    user_role = request.data.get('user_role', 'Staff')

    if user_id and user_role != 'Admin':
        try:
            user = SystemUser.objects.get(pk=user_id)
            user.is_online  = False
            user.status     = 'Inactive'   # ← sync status on logout
            user.last_seen  = timezone.now()
            user.save(update_fields=['is_online', 'last_seen', 'status'])
        except SystemUser.DoesNotExist:
            pass

    log_action(
        f'Signed out: {user_name} ({user_role})',
        'Auth',
        user_name,
        False,
        user_role,
        'Active' if user_role == 'Admin' else 'Inactive'
    )
    return Response({'ok': True})


@api_view(['POST'])
def auth_register(request):
    serializer = SystemUserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        log_action(f'New user registered: {user.name}', 'User', user.name)
        return Response(SystemUserPublicSerializer(user).data, status=201)
    return Response(serializer.errors, status=400)


# ─── HEARTBEAT ─────────────────────────────────────────────────────────────────

@api_view(['POST'])
def auth_heartbeat(request):
    user_id = request.data.get('user_id')
    if not user_id:
        return Response({'ok': False, 'msg': 'user_id required.'}, status=400)
    try:
        user = SystemUser.objects.get(pk=user_id)
        if user.role != 'Admin':
            user.is_online = True
            user.status    = 'Active'      # ← keep status in sync on heartbeat
            user.last_seen = timezone.now()
            user.save(update_fields=['is_online', 'last_seen', 'status'])
        return Response({'ok': True})
    except SystemUser.DoesNotExist:
        return Response({'ok': False, 'msg': 'User not found.'}, status=404)


# ─── MARK OFFLINE ──────────────────────────────────────────────────────────────

@api_view(['POST'])
def auth_offline(request):
    user_id   = request.data.get('user_id')
    user_name = request.data.get('user_name', '')
    if not user_id:
        return Response({'ok': False, 'msg': 'user_id required.'}, status=400)
    try:
        user = SystemUser.objects.get(pk=user_id)
        if user.role != 'Admin':
            user.is_online = False
            user.status    = 'Inactive'    # ← sync status when going offline
            user.last_seen = timezone.now()
            user.save(update_fields=['is_online', 'last_seen', 'status'])
            log_action(
                f'{user.name} went offline',
                'Auth',
                user.name,
                False,
                user.role,
                'Inactive'
            )
        return Response({'ok': True})
    except SystemUser.DoesNotExist:
        return Response({'ok': False, 'msg': 'User not found.'}, status=404)


# ─── USERS ─────────────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
def users_list(request):
    if request.method == 'GET':
        two_min_ago = timezone.now() - timezone.timedelta(minutes=2)
        # Auto-expire stale online Staff — sync both is_online AND status
        SystemUser.objects.filter(
            is_online=True,
            last_seen__lt=two_min_ago,
            role='Staff'
        ).update(is_online=False, status='Inactive')

        users = SystemUser.objects.all()
        return Response(SystemUserPublicSerializer(users, many=True).data)

    serializer = SystemUserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        log_action(f'User added: {user.name}', 'User')
        return Response(SystemUserPublicSerializer(user).data, status=201)
    return Response(serializer.errors, status=400)


@api_view(['GET', 'PATCH', 'PUT', 'DELETE'])
def users_detail(request, pk):
    try:
        user = SystemUser.objects.get(pk=pk)
    except SystemUser.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=404)

    if request.method == 'GET':
        return Response(SystemUserPublicSerializer(user).data)

    if request.method in ['PATCH', 'PUT']:
        data = request.data.copy()
        if not data.get('password'):
            data.pop('password', None)

        # Prevent manual override of status — always derive from role + is_online
        if data.get('role') == 'Admin':
            data['status'] = 'Active'
        else:
            # Keep current is_online state, don't let form overwrite it
            data['status'] = 'Active' if user.is_online else 'Inactive'

        serializer = SystemUserSerializer(user, data=data, partial=True)
        if serializer.is_valid():
            user = serializer.save()
            log_action(f'User updated: {user.name}', 'User')
            return Response(SystemUserPublicSerializer(user).data)
        return Response(serializer.errors, status=400)

    if request.method == 'DELETE':
        name = user.name
        user.delete()
        log_action(f'User deleted: {name}', 'User', urgent=True)
        return Response(status=204)


# ─── INCIDENTS ─────────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
def incidents_list(request):
    if request.method == 'GET':
        incidents = Incident.objects.all()
        return Response(IncidentSerializer(incidents, many=True).data)

    serializer = IncidentSerializer(data=request.data)
    if serializer.is_valid():
        inc = serializer.save()
        log_action(
            f'{inc.type} incident in {inc.zone}',
            'Incident',
            request.data.get('reporter', 'System'),
            inc.severity == 'High'
        )
        return Response(IncidentSerializer(inc).data, status=201)
    return Response(serializer.errors, status=400)


@api_view(['GET', 'PATCH', 'PUT', 'DELETE'])
def incidents_detail(request, pk):
    try:
        inc = Incident.objects.get(pk=pk)
    except Incident.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=404)

    if request.method == 'GET':
        return Response(IncidentSerializer(inc).data)

    if request.method in ['PATCH', 'PUT']:
        serializer = IncidentSerializer(inc, data=request.data, partial=True)
        if serializer.is_valid():
            inc = serializer.save()
            log_action(f'Incident updated: {inc.type} in {inc.zone}', 'Incident')
            return Response(IncidentSerializer(inc).data)
        return Response(serializer.errors, status=400)

    if request.method == 'DELETE':
        label = f'{inc.type} in {inc.zone}'
        inc.delete()
        log_action(f'Incident deleted: {label}', 'Incident', urgent=True)
        return Response(status=204)


# ─── ALERTS ────────────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
def alerts_list(request):
    if request.method == 'GET':
        alerts = Alert.objects.all()
        return Response(AlertSerializer(alerts, many=True).data)

    serializer = AlertSerializer(data=request.data)
    if serializer.is_valid():
        alert = serializer.save()
        log_action(
            f'{alert.level} alert sent to {alert.zone}',
            'Alert',
            alert.sent_by,
            alert.level == 'Danger'
        )
        return Response(AlertSerializer(alert).data, status=201)
    return Response(serializer.errors, status=400)


@api_view(['GET', 'PATCH', 'PUT', 'DELETE'])
def alerts_detail(request, pk):
    try:
        alert = Alert.objects.get(pk=pk)
    except Alert.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=404)

    if request.method == 'GET':
        return Response(AlertSerializer(alert).data)

    if request.method in ['PATCH', 'PUT']:
        serializer = AlertSerializer(alert, data=request.data, partial=True)
        if serializer.is_valid():
            alert = serializer.save()
            return Response(AlertSerializer(alert).data)
        return Response(serializer.errors, status=400)

    if request.method == 'DELETE':
        alert.delete()
        log_action('Alert deleted', 'Alert')
        return Response(status=204)


# ─── EVAC CENTERS ──────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
def evac_list(request):
    if request.method == 'GET':
        centers = EvacCenter.objects.all()
        return Response(EvacCenterSerializer(centers, many=True).data)

    serializer = EvacCenterSerializer(data=request.data)
    if serializer.is_valid():
        center = serializer.save()
        log_action(f'Evac center added: {center.name}', 'Evacuation')
        return Response(EvacCenterSerializer(center).data, status=201)
    return Response(serializer.errors, status=400)


@api_view(['GET', 'PATCH', 'PUT', 'DELETE'])
def evac_detail(request, pk):
    try:
        center = EvacCenter.objects.get(pk=pk)
    except EvacCenter.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=404)

    if request.method == 'GET':
        return Response(EvacCenterSerializer(center).data)

    if request.method in ['PATCH', 'PUT']:
        serializer = EvacCenterSerializer(center, data=request.data, partial=True)
        if serializer.is_valid():
            center = serializer.save()
            log_action(f'Evac center updated: {center.name}', 'Evacuation')
            return Response(EvacCenterSerializer(center).data)
        return Response(serializer.errors, status=400)

    if request.method == 'DELETE':
        name = center.name
        center.delete()
        log_action(f'Evac center deleted: {name}', 'Evacuation', urgent=True)
        return Response(status=204)


# ─── RESIDENTS ─────────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
def residents_list(request):
    if request.method == 'GET':
        residents = Resident.objects.all()
        return Response(ResidentSerializer(residents, many=True).data)

    serializer = ResidentSerializer(data=request.data)
    if serializer.is_valid():
        resident = serializer.save()
        log_action(
            f'Resident added: {resident.name} ({resident.zone})',
            'Resident',
            request.data.get('added_by', 'Mobile')
        )
        return Response(ResidentSerializer(resident).data, status=201)
    return Response(serializer.errors, status=400)


@api_view(['GET', 'PATCH', 'PUT', 'DELETE'])
def residents_detail(request, pk):
    try:
        resident = Resident.objects.get(pk=pk)
    except Resident.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=404)

    if request.method == 'GET':
        return Response(ResidentSerializer(resident).data)

    if request.method in ['PATCH', 'PUT']:
        serializer = ResidentSerializer(resident, data=request.data, partial=True)
        if serializer.is_valid():
            resident = serializer.save()
            log_action(f'Resident updated: {resident.name}', 'Resident')
            return Response(ResidentSerializer(resident).data)
        return Response(serializer.errors, status=400)

    if request.method == 'DELETE':
        name = resident.name
        resident.delete()
        log_action(f'Resident deleted: {name}', 'Resident', urgent=True)
        return Response(status=204)


# ─── RESOURCES ─────────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
def resources_list(request):
    if request.method == 'GET':
        resources = Resource.objects.all()
        return Response(ResourceSerializer(resources, many=True).data)

    serializer = ResourceSerializer(data=request.data)
    if serializer.is_valid():
        res = serializer.save()
        log_action(f'Resource added: {res.name}', 'Resource')
        return Response(ResourceSerializer(res).data, status=201)
    return Response(serializer.errors, status=400)


@api_view(['GET', 'PATCH', 'PUT', 'DELETE'])
def resources_detail(request, pk):
    try:
        resource = Resource.objects.get(pk=pk)
    except Resource.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=404)

    if request.method == 'GET':
        return Response(ResourceSerializer(resource).data)

    if request.method in ['PATCH', 'PUT']:
        serializer = ResourceSerializer(resource, data=request.data, partial=True)
        if serializer.is_valid():
            resource = serializer.save()
            log_action(f'Resource updated: {resource.name}', 'Resource')
            return Response(ResourceSerializer(resource).data)
        return Response(serializer.errors, status=400)

    if request.method == 'DELETE':
        name = resource.name
        resource.delete()
        log_action(f'Resource deleted: {name}', 'Resource', urgent=True)
        return Response(status=204)


# ─── ACTIVITY LOG ──────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
def activity_log_list(request):
    if request.method == 'GET':
        logs = ActivityLog.objects.all()[:200]
        return Response(ActivityLogSerializer(logs, many=True).data)

    serializer = ActivityLogSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)


# ─── DASHBOARD SUMMARY ─────────────────────────────────────────────────────────

@api_view(['GET'])
def dashboard_summary(request):
    active_incidents = Incident.objects.filter(status__in=['Active', 'Pending']).count()
    total_residents  = Resident.objects.count()
    evacuated        = Resident.objects.filter(evacuation_status='Evacuated').count()
    unaccounted      = Resident.objects.filter(evacuation_status='Unaccounted').count()
    open_centers     = EvacCenter.objects.filter(status='Open').count()
    total_cap        = sum(EvacCenter.objects.values_list('capacity', flat=True))
    total_occ        = sum(EvacCenter.objects.values_list('occupancy', flat=True))

    return Response({
        'incidents': {
            'total':    Incident.objects.count(),
            'active':   active_incidents,
            'resolved': Incident.objects.filter(status='Resolved').count(),
        },
        'alerts':    Alert.objects.count(),
        'residents': {
            'total':       total_residents,
            'evacuated':   evacuated,
            'unaccounted': unaccounted,
            'safe':        Resident.objects.filter(evacuation_status='Safe').count(),
        },
        'evacuation': {
            'open_centers':    open_centers,
            'total_centers':   EvacCenter.objects.count(),
            'total_capacity':  total_cap,
            'total_occupancy': total_occ,
        },
        'resources': Resource.objects.count(),
    })