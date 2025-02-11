from rest_framework import serializers
from .models import Post

class PostSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    author = serializers.CharField()  # Store as author ID
    title = serializers.CharField(max_length=255)
    description = serializers.CharField()
    content = serializers.CharField()
    formatted_content = serializers.SerializerMethodField()
    contentType = serializers.ChoiceField(choices=[('text/plain', 'Plain Text'), ('text/markdown', 'Markdown')])
    published= serializers.DateTimeField()
    visibility = serializers.ChoiceField(choices=["PUBLIC", "FRIENDS", "UNLISTED"])

    def get_formatted_content(self, obj):
        """Convert Markdown content to HTML if applicable."""
        return obj.get_formatted_content()

    def create(self, validated_data):
        """Create a new Post instance."""
        return Post.objects.create(**validated_data)

    def update(self, instance, validated_data):
        """Update an existing Post instance."""
        instance.title = validated_data.get('title', instance.title)
        instance.description = validated_data.get('description', instance.description)
        instance.content = validated_data.get('content', instance.content)
        instance.contentType = validated_data.get('contentType', instance.contentType)
        instance.visibility = validated_data.get('visibility', instance.visibility)
        instance.save()
        return instance