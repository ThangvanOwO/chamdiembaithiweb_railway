from rest_framework import serializers
from .models import Classroom, Student, SupportTicket


class ClassroomInput(serializers.ModelSerializer):
    class Meta:
        model = Classroom
        fields = ['name', 'school_year', 'archived']


class StudentInput(serializers.ModelSerializer):
    student_id = serializers.CharField(max_length=50, trim_whitespace=True)

    class Meta:
        model = Student
        fields = ['name', 'student_id', 'archived']


class TicketInput(serializers.ModelSerializer):
    message = serializers.CharField(max_length=4000, min_length=5)
    technical = serializers.JSONField(required=False)

    class Meta:
        model = SupportTicket
        fields = ['message', 'technical', 'image']

    def validate_technical(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('Thông tin kỹ thuật không hợp lệ.')
        allowed = {'version', 'build', 'platform', 'os', 'screen'}
        return {k: str(v)[:200] for k, v in value.items() if k in allowed}

    def validate_image(self, image):
        if image.size > 5 * 1024 * 1024:
            raise serializers.ValidationError('Ảnh tối đa 5 MB.')
        if image.image.format not in {'JPEG', 'PNG', 'WEBP'}:
            raise serializers.ValidationError('Chọn ảnh JPEG, PNG hoặc WebP.')
        return image
