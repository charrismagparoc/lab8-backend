from django.db import models
import uuid


class SystemUser(models.Model):
    ROLE_CHOICES = [('Admin', 'Admin'), ('Staff', 'Staff')]
    STATUS_CHOICES = [('Active', 'Active'), ('Inactive', 'Inactive')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=200)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Staff')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    last_login = models.DateTimeField(null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    is_online = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'system_users'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.role})"


class Incident(models.Model):
    SEVERITY_CHOICES = [('Low', 'Low'), ('Medium', 'Medium'), ('High', 'High')]
    STATUS_CHOICES = [
        ('Active', 'Active'), ('Pending', 'Pending'), ('Verified', 'Verified'),
        ('Responded', 'Responded'), ('Resolved', 'Resolved')
    ]
    TYPE_CHOICES = [
        ('Flood', 'Flood'), ('Fire', 'Fire'), ('Earthquake', 'Earthquake'),
        ('Landslide', 'Landslide'), ('Storm', 'Storm')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    zone = models.CharField(max_length=50)
    location = models.TextField(blank=True, default='')
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='Medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    description = models.TextField(blank=True, default='')
    reporter = models.CharField(max_length=200, blank=True, default='')
    source = models.CharField(max_length=20, default='web')
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    date_reported = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'incidents'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.type} - {self.zone} ({self.status})"


class Alert(models.Model):
    LEVEL_CHOICES = [
        ('Advisory', 'Advisory'), ('Warning', 'Warning'),
        ('Danger', 'Danger'), ('Resolved', 'Resolved')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300, blank=True, default='')
    message = models.TextField()
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='Advisory')
    zone = models.CharField(max_length=100, default='All Zones')
    channel = models.CharField(max_length=50, default='Web')
    sent_by = models.CharField(max_length=200, default='Admin')
    recipients_count = models.IntegerField(default=0)
    sent_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'alerts'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.level} - {self.zone}"


class EvacCenter(models.Model):
    STATUS_CHOICES = [('Open', 'Open'), ('Full', 'Full'), ('Closed', 'Closed')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=300)
    zone = models.CharField(max_length=50)
    address = models.TextField(blank=True, default='')
    capacity = models.IntegerField(default=0)
    occupancy = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Open')
    facilities_available = models.JSONField(default=list, blank=True)
    contact_person = models.CharField(max_length=200, blank=True, default='')
    contact = models.CharField(max_length=50, blank=True, default='')
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'evac_centers'
        ordering = ['zone', 'name']

    def __str__(self):
        return f"{self.name} ({self.status})"


class Resident(models.Model):
    EVAC_STATUS_CHOICES = [
        ('Safe', 'Safe'), ('Evacuated', 'Evacuated'), ('Unaccounted', 'Unaccounted')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=300)
    zone = models.CharField(max_length=50)
    address = models.TextField(blank=True, default='')
    household_members = models.IntegerField(default=1)
    contact = models.CharField(max_length=50, blank=True, default='')
    evacuation_status = models.CharField(
        max_length=20, choices=EVAC_STATUS_CHOICES, default='Safe'
    )
    vulnerability_tags = models.JSONField(default=list, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    added_by = models.CharField(max_length=200, default='Mobile')
    source = models.CharField(max_length=20, default='mobile')
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'residents'
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.name} - {self.zone} ({self.evacuation_status})"


class Resource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=300)
    category = models.CharField(max_length=100)
    quantity = models.IntegerField(default=0)
    available = models.IntegerField(default=0)
    unit = models.CharField(max_length=50, default='pcs')
    location = models.CharField(max_length=300, blank=True, default='')
    status = models.CharField(max_length=50, default='Available')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'resources'
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} ({self.category})"


class ActivityLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action = models.TextField()
    type = models.CharField(max_length=50)
    user_name = models.CharField(max_length=200, default='System')
    user_role = models.CharField(max_length=20, default='System')
    user_status = models.CharField(max_length=20, default='')
    urgent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'activity_log'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.type}] {self.action}"