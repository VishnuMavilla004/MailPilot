# Create your models here.
from django.conf import settings
from django.db import models
from cryptography.fernet import Fernet

from django.conf import settings
from django.db import models
from cryptography.fernet import Fernet

def _fernet():
    return Fernet(settings.TOKEN_ENCRYPTION_KEY.encode())

class GoogleCredential(models.Model):
    """Stores the user's Google tokens so we can call Gmail/Calendar later."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    google_id = models.CharField(max_length=64, unique=True)
    access_token_enc = models.TextField()
    refresh_token_enc = models.TextField(blank=True)
    token_expiry = models.DateTimeField(null=True)
    scopes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def set_tokens(self, access, refresh=None):
        self.access_token_enc = _fernet().encrypt(access.encode()).decode()
        if refresh:
            self.refresh_token_enc = _fernet().encrypt(refresh.encode()).decode()

    def get_access_token(self):
        return _fernet().decrypt(self.access_token_enc.encode()).decode()

    def get_refresh_token(self):
        return _fernet().decrypt(self.refresh_token_enc.encode()).decode() if self.refresh_token_enc else None