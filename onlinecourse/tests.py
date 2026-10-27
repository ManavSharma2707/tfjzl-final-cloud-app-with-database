from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Choice, Course, Enrollment, Question, Submission


class ExamFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('learner', password='pw12345!', first_name='Lea')
        self.course = Course.objects.create(name='Cloud', description='d', image='x.jpg')
        self.q1 = Question.objects.create(course=self.course, question_text='Q1', grade=50)
        self.q1a = Choice.objects.create(question=self.q1, choice_text='right', is_correct=True)
        self.q1b = Choice.objects.create(question=self.q1, choice_text='wrong', is_correct=False)
        self.q2 = Question.objects.create(course=self.course, question_text='Q2', grade=50)
        self.q2a = Choice.objects.create(question=self.q2, choice_text='r1', is_correct=True)
        self.q2b = Choice.objects.create(question=self.q2, choice_text='r2', is_correct=True)
        self.q2c = Choice.objects.create(question=self.q2, choice_text='w', is_correct=False)
        self.client.login(username='learner', password='pw12345!')
        Enrollment.objects.create(user=self.user, course=self.course, mode='honor')

    def _submit(self, *choices):
        data = {'choice_%d' % c.id: c.id for c in choices}
        return self.client.post(reverse('onlinecourse:submit', args=(self.course.id,)), data)

    def test_detail_shows_exam(self):
        resp = self.client.get(reverse('onlinecourse:course_details', args=(self.course.id,)))
        self.assertContains(resp, 'Q1')
        self.assertContains(resp, 'name="choice_%d"' % self.q1a.id)

    def test_detail_hides_exam_when_anonymous(self):
        self.client.logout()
        resp = self.client.get(reverse('onlinecourse:course_details', args=(self.course.id,)))
        self.assertNotContains(resp, 'questionform')

    def test_all_correct_passes(self):
        resp = self._submit(self.q1a, self.q2a, self.q2b)
        sub = Submission.objects.get()
        self.assertRedirects(resp, reverse('onlinecourse:show_exam_result', args=(self.course.id, sub.id)))
        self.assertEqual(sub.choices.count(), 3)
        resp = self.client.get(resp.url)
        self.assertEqual(resp.context['grade'], 100)
        self.assertContains(resp, 'Congratulations')

    def test_partial_multi_answer_fails_question(self):
        resp = self._submit(self.q1a, self.q2a)  # q2 needs both r1 and r2
        resp = self.client.get(resp.url)
        self.assertEqual(resp.context['grade'], 50)
        self.assertContains(resp, 'Failed')
        self.assertContains(resp, 'Re-test')

    def test_wrong_extra_choice_fails_question(self):
        resp = self._submit(self.q1a, self.q1b, self.q2a, self.q2b)
        resp = self.client.get(resp.url)
        self.assertEqual(resp.context['grade'], 50)

    def test_nothing_selected(self):
        resp = self.client.get(self._submit().url)
        self.assertEqual(resp.context['grade'], 0)

    def test_submit_requires_enrollment(self):
        Enrollment.objects.all().delete()
        self.assertEqual(self._submit(self.q1a).status_code, 404)
