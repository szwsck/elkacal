import csv
import datetime as dt
import pickle
from typing import NamedTuple, Callable

import arrow
import inquirer
from ics import Calendar, Event
from ics.parse import ContentLine
from ics.utils import arrow_to_iso

WEEKDAY_CHOICES = [
    ('Monday', 1),
    ('Tuesday', 2),
    ('Wednesday', 3),
    ('Thursday', 4),
    ('Friday', 5)
]

PARITY_CHOICES = [
    ('Weekly', ('N', 'P', 'N/P')),
    ('Even weeks', ('P',)),
    ('Odd weeks', ('N',)),
    ('Custom', ())
]

DISPLAY_TIME_FMT = '%H:%M'


class ElkaDay(NamedTuple):
    """Description of a single day of teaching"""
    date: dt.date
    parity: str
    weekday: int

    def __str__(self):
        return self.date.strftime(f'%a {self.parity}, %-d %b %Y')


class ElkaCourse(NamedTuple):
    """A periodic event that happens on a given time and weekday (possibly not every week)"""
    name: str
    description: str
    location: str
    start_time: dt.time
    end_time: dt.time
    days: list[ElkaDay]

    def __str__(self):
        return '{}{} on {} at {} in {} ({} classes)'.format(
            self.name,
            f'({self.description})' if self.description else '',
            self.days[0].date.strftime('%a'),
            self.start_time.strftime(DISPLAY_TIME_FMT),
            self.location,
            len(self.days)
        )


class MenuOption(NamedTuple):
    title: str
    action: Callable


def load_semester(sem_code: str) -> list[ElkaDay]:
    days = []

    with open(f'{sem_code}.csv', 'r') as file:
        reader = csv.reader(file)
        for date_str, parity, weekday_str in reader:
            date = dt.datetime.strptime(date_str, '%Y-%m-%d').date()
            days.append(ElkaDay(
                date,
                parity,
                int(weekday_str) if weekday_str else date.isoweekday()
            ))

    return days


def create_course(semester: list[ElkaDay]) -> ElkaCourse:
    name = inquirer.text('Course name')
    description = inquirer.text('Description')
    location = inquirer.text('Location')

    weekday = inquirer.list_input('Weekday', choices=WEEKDAY_CHOICES)

    start_time_str = inquirer.text(
        'Start time',
        validate=lambda _, v: dt.datetime.strptime(v, DISPLAY_TIME_FMT)
    )
    start_time = dt.datetime.strptime(start_time_str, DISPLAY_TIME_FMT).time()

    end_time_default = (dt.datetime.combine(dt.date(1, 1, 1), start_time) + dt.timedelta(minutes=105)).time()
    end_time_str = inquirer.text(
        'End time',
        default=end_time_default.strftime(DISPLAY_TIME_FMT),
        validate=lambda _, v: dt.datetime.strptime(v, DISPLAY_TIME_FMT).time() > start_time
    )
    end_time = dt.datetime.strptime(end_time_str, DISPLAY_TIME_FMT).time()

    parities = inquirer.list_input('Frequency', choices=PARITY_CHOICES)

    days_all = [d for d in semester if d.weekday == weekday]
    days_default = [d for d in days_all if d.parity in parities]
    days_selected = inquirer.checkbox(
        'Class dates',
        choices=[d for d in days_all],
        default=days_default
    )

    return ElkaCourse(name, description, location, start_time, end_time, days_selected)


def remove_course(courses: list[ElkaCourse], course: ElkaCourse):
    confirm = inquirer.list_input(
        f'Do you want to remove course {course.name}?',
        choices=[
            ('Yes', True),
            ('No', False)
        ])

    if confirm:
        courses.remove(course)


def export(cal_name: str, courses: list[ElkaCourse]):
    calendar = Calendar()
    for course in courses:
        event = Event(
            name=course.name, description=course.description, location=course.location,
            begin=arrow.get(dt.datetime.combine(course.days[0].date, course.start_time), 'local'),
            end=arrow.get(dt.datetime.combine(course.days[0].date, course.end_time), 'local'),
        )
        # use extra field to specify recurrence dates because ics lib doesn't support it
        # field format from here: https://datatracker.ietf.org/doc/html/rfc5545#section-3.8.5.2
        recurrences = [arrow.get(dt.datetime.combine(d.date, course.start_time), 'local') for d in course.days]
        event.extra.append(ContentLine('RDATE', value=','.join(arrow_to_iso(d) for d in recurrences)))

        calendar.events.add(event)

    with open(f'{cal_name}.ics', 'w') as f:
        f.writelines(calendar)

    print(f'Exported to {cal_name}.ics')


def show_menu(menu: list[MenuOption]):
    choice = inquirer.list_input(
        message='Choose an action',
        choices=[(opt.title, opt) for opt in menu]
    )

    choice.action()


def main():
    cal_name = inquirer.text('Calendar name')
    semester = load_semester('22L')

    while True:
        try:
            courses = pickle.load(open(f'{cal_name}.pickle', 'rb'))
        except FileNotFoundError:
            courses = []

        main_menu = [
            MenuOption('Add course', lambda: courses.append(create_course(semester)))
        ]

        for i, course in enumerate(courses):
            main_menu.append(MenuOption(f'Remove {course}', lambda c=course: remove_course(courses, c)))

        main_menu.append(MenuOption('Export to .ics', lambda: export(cal_name, courses)))
        main_menu.append(MenuOption('Save and exit', lambda: exit()))

        show_menu(main_menu)

        pickle.dump(courses, open(f'{cal_name}.pickle', 'wb'))


if __name__ == '__main__':
    main()
