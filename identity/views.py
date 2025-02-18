from django.views.generic import DetailView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from posts.models import Post  
from identity.models import Author

class AuthorProfileView(DetailView):
    model = Author
    template_name = 'identity/author_profile.html'
    context_object_name = 'author'
    
    def get_object(self):
        return get_object_or_404(Author, user__username=self.kwargs['username'])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        author = self.get_object()
        # Add public posts to profile
        context['posts'] = Post.objects.filter(
            author=author,
            visibility='PUBLIC'
        ).order_by('-published')
        return context

class AuthorListView(ListView):
    model = Author
    template_name = 'authors/author_list.html'
    context_object_name = 'authors'
    paginate_by = 10