from django import forms

class LeadForm(forms.Form):
    name = forms.CharField(label='Ваше имя', max_length=100,
                           widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ваше имя'}))
    email = forms.EmailField(label='Ваш Email',
                            widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Ваш Email'}))
    phone = forms.CharField(label='Ваш телефон', max_length=20, required=False,
                            widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ваш телефон'}))
    message = forms.CharField(label='Сообщение', widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ваше сообщение'}),
                              required=False)
    item_pk = forms.IntegerField(widget=forms.HiddenInput())
