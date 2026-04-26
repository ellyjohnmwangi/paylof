from rest_framework.permissions import BasePermission


def get_profile(user):
    if not user or not user.is_authenticated:
        return None
    return getattr(user, 'profile', None)


class HasBusinessProfile(BasePermission):
    message = 'Your account is not attached to an SME business.'

    def has_permission(self, request, view):
        return bool(get_profile(request.user))


class HasCapability(BasePermission):
    capability = None
    message = 'You do not have access to this workspace.'

    def has_permission(self, request, view):
        profile = get_profile(request.user)
        return bool(profile and profile.can(self.capability))


class CanSell(HasCapability):
    capability = 'sales'
    message = 'Only users with sales access can process transactions.'


class CanManageInventory(HasCapability):
    capability = 'inventory'
    message = 'Only owners and managers can manage inventory.'


class CanViewReports(HasCapability):
    capability = 'reports'
    message = 'Only owners and managers can view reports.'


class CanManageUsers(HasCapability):
    capability = 'users'
    message = 'Only owners and managers can manage users.'


class CanManageDistributors(HasCapability):
    capability = 'distributors'
    message = 'Only owners and managers can manage distributors.'
