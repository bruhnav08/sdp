from django import forms
from room_inventory.models import Amenity, GuestHouse, Room, RoomCategory


class GuestHouseForm(forms.ModelForm):
    class Meta:
        model = GuestHouse
        fields = ["name", "campus", "contact_number", "description", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. KE Hall, DVK Guest House"}),
            "campus": forms.Select(attrs={"class": "form-control"}),
            "contact_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "Contact Number"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Guest House details"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class RoomCategoryForm(forms.ModelForm):
    class Meta:
        model = RoomCategory
        fields = ["name", "guest_house", "default_capacity", "description", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Single, Double King, Double Queen, Double Twin"}),
            "guest_house": forms.Select(attrs={"class": "form-control"}),
            "default_capacity": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class RoomForm(forms.ModelForm):
    amenities = forms.ModelMultipleChoiceField(
        queryset=Amenity.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "amenities-grid"}),
        required=False,
    )

    class Meta:
        model = Room
        fields = ["room_number", "floor", "capacity", "guest_house", "room_category", "amenities", "status", "is_active"]
        widgets = {
            "room_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. 101, 202A"}),
            "floor": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Ground Floor, 1, 2"}),
            "capacity": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "guest_house": forms.Select(attrs={"class": "form-control"}),
            "room_category": forms.Select(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class AmenityForm(forms.ModelForm):
    class Meta:
        model = Amenity
        fields = ["name", "icon", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Wi-Fi, AC, TV"}),
            "icon": forms.TextInput(attrs={"class": "form-control", "placeholder": "Icon or emoji (optional)"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
