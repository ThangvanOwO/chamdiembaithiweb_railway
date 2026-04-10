from django import forms
from .models import Exam


class ExamForm(forms.ModelForm):
    """Form for creating/editing exams."""

    class Meta:
        model = Exam
        fields = ['title', 'subject', 'num_questions', 'answer_key']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'VD: Kiểm tra Toán chương 1',
                'id': 'exam-title',
            }),
            'subject': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'VD: Toán, Lý, Hóa...',
                'id': 'exam-subject',
            }),
            'num_questions': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': 1,
                'max': 200,
                'id': 'exam-questions',
            }),
            'answer_key': forms.Textarea(attrs={
                'class': 'form-textarea',
                'placeholder': 'A,B,C,D,A,B,C,D,...',
                'rows': 4,
                'id': 'exam-answers',
            }),
        }
        labels = {
            'title': 'Tên bài thi',
            'subject': 'Môn',
            'num_questions': 'Số câu hỏi',
            'answer_key': 'Đáp án đúng',
        }
        help_texts = {
            'answer_key': 'Nhập đáp án theo thứ tự, phân cách bởi dấu phẩy. VD: A,B,C,D,A,B,...',
        }


class UploadForm(forms.Form):
    """Form for uploading exam images."""
    exam = forms.ModelChoiceField(
        queryset=Exam.objects.none(),
        label='Chọn bài thi',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'upload-exam-select',
        })
    )
    # Note: File input is handled in the template directly (multi-file via Alpine.js)

    def __init__(self, *args, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        if teacher:
            self.fields['exam'].queryset = Exam.objects.filter(teacher=teacher)
