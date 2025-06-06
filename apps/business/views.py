from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Business, PaymentMethods, Review
from .serializers import BusinessSerializer, PaymentMethodsSerializer, ReviewSerializer
from django.db import models
from rest_framework import serializers
from rest_framework.permissions import IsAdminUser


class BusinessViewSet(viewsets.ModelViewSet):
    queryset = Business.objects.all()
    serializer_class = BusinessSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        # Users can only see their own businesses or verified businesses
        return Business.objects.filter(
            models.Q(owner=self.request.user) | models.Q(is_verified=True)
        )

    @action(detail=True, methods=['GET'])
    def payment_methods(self, request, slug=None):
        business = self.get_object()
        payment_methods = business.payment_methods.all()
        serializer = PaymentMethodsSerializer(payment_methods, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def verify(self, request, slug=None):
        business = self.get_object()
        business.verification_status = 'verified'
        business.verified_at = timezone.now()
        business.save()
        return Response({'status': 'Business verified'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, slug=None):
        business = self.get_object()
        business.verification_status = 'rejected'
        business.save()
        return Response({'status': 'Business rejected'})

class PaymentMethodsViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentMethodsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Users can only see payment methods of their own businesses
        return PaymentMethods.objects.filter(business__owner=self.request.user)

class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Filter reviews based on business or user context
        return Review.objects.filter(
            models.Q(product__owner=self.request.user) | 
            models.Q(user=self.request.user)
        )

    def perform_create(self, serializer):
        # Validate that the user hasn't already reviewed this business
        business_id = self.request.data.get('product')
        existing_review = Review.objects.filter(
            user=self.request.user, 
            product_id=business_id
        ).exists()
        
        if existing_review:
            raise serializers.ValidationError(
                "You have already reviewed this business."
            )
        
        serializer.save(user=self.request.user)