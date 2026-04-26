from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Business, UserProfile


class AuthAndRoleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.business = Business.objects.create(name='Role Test Shop')
        self.owner = User.objects.create_user(username='owner', password='password123')
        UserProfile.objects.create(
            user=self.owner,
            business=self.business,
            role=UserProfile.ROLE_OWNER,
        )
        self.cashier = User.objects.create_user(username='cashier', password='password123')
        UserProfile.objects.create(
            user=self.cashier,
            business=self.business,
            role=UserProfile.ROLE_CASHIER,
        )

    def test_login_returns_token_and_capabilities(self):
        response = self.client.post(
            '/api/auth/login/',
            {'username': 'owner', 'password': 'password123'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.data)
        self.assertIn('users', response.data['user']['profile']['capabilities'])

    def test_owner_can_create_user(self):
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            '/api/users/',
            {
                'username': 'newcashier',
                'password': 'password123',
                'email': 'new@example.com',
                'role': UserProfile.ROLE_CASHIER,
                'phone': '0711000000',
                'is_active': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(username='newcashier').exists())

    def test_owner_can_generate_password_reset_link(self):
        self.client.force_authenticate(self.owner)

        response = self.client.post(f'/api/users/{self.cashier.id}/send_password_reset/')

        self.assertEqual(response.status_code, 200)
        self.assertIn('/reset-password/', response.data['reset_link'])

    def test_cashier_cannot_manage_users(self):
        self.client.force_authenticate(self.cashier)

        response = self.client.get('/api/users/')

        self.assertEqual(response.status_code, 403)
