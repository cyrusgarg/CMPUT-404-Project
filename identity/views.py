from django.views.generic import DetailView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from .models import Author  

class AuthorProfileView(DetailView):
    model = Author
    template_name = 'identity/author_profile.html'
    context_object_name = 'author'
    
    def get_object(self):
        return get_object_or_404(Author, user__username=self.kwargs['username'])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add additional context if needed
        return context

class AuthorListView(ListView):
    model = Author
    template_name = 'authors/author_list.html'
    context_object_name = 'authors'
    paginate_by = 10