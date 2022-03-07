import csv
import datetime as dt
from typing import NamedTuple

import arrow
import inquirer
from ics import Calendar, Event

TIME_FMT = '%H:%M'
DATE_FMT = '%Y-%m-%d'


class ElkaDay(NamedTuple):
    date: dt.date
    parity: str
    weekday: int

    def __str__(self):
        return self.date.strftime(f'%a {self.parity}, %-d %b %Y')


class ElkaClass(NamedTuple):
    name: str
    description: str
    location: str
    start_time: dt.time
    end_time: dt.time
    days: list[ElkaDay]

    def __str__(self):
        return " - {} on {} at {} ({} events)".format(
            self.name,
            self.days[0].date.strftime('%a'),
            self.start_time.strftime(TIME_FMT),
            len(self.days)
        )


# parse csv calendar file

days = []
with open('22L.csv', 'r') as file:
    reader = csv.reader(file)
    for date_str, parity_str, weekday_str in reader:
        date = dt.datetime.strptime(date_str, DATE_FMT).date()
        days.append(ElkaDay(
            date,
            parity_str if parity_str else None,
            int(weekday_str) if weekday_str else date.isoweekday()
        ))

classes = []

# add class loop

while True:
    name = inquirer.text('Class name')
    description = inquirer.text('Description')
    location = inquirer.text('Location')

    weekday = inquirer.list_input(
        'Weekday',
        choices=[
            ('Monday', 1),
            ('Tuesday', 2),
            ('Wednesday', 3),
            ('Thursday', 4),
            ('Friday', 5)
        ],
        default=1)

    start_time_str = inquirer.text(
        'Start time',
        validate=lambda _, v: dt.datetime.strptime(v, TIME_FMT)
    )
    start_time = dt.datetime.strptime(start_time_str, TIME_FMT).time()

    end_time_default = (dt.datetime.combine(dt.date(1, 1, 1), start_time) + dt.timedelta(minutes=105)).time()
    end_time_str = inquirer.text(
        'End time',
        default=end_time_default.strftime(TIME_FMT),
        validate=lambda _, v: dt.datetime.strptime(v, TIME_FMT).time() > start_time
    )
    end_time = dt.datetime.strptime(end_time_str, TIME_FMT).time()

    frequency = inquirer.list_input(
        'Frequency',
        choices=[
            ('Weekly', ''),
            ('Even weeks', 'P'),
            ('Odd weeks', 'N'),
            ('Custom', 'X')
        ],
        default='NP')

    days_shown = [(str(d), d) for d in days if d.weekday == weekday]
    days_default = [d for d in days if d.weekday == weekday and frequency in d.parity]
    days_selected = inquirer.checkbox('Event dates', choices=days_shown, default=days_default)

    classes.append(ElkaClass(name, description, location, start_time, end_time, days_selected))

    print('Current classes:')
    for cls in classes:
        print(cls)
    print('')

    add_another = inquirer.list_input(
        "Continue?",
        default=True,
        choices=[('Add another class', True), ('Save to file and exit', False)]
    )

    if not add_another:
        break

# add events to calendar

calendar = Calendar()
for cls in classes:
    for day in cls.days:
        calendar.events.add(Event(
            name=cls.name,
            begin=arrow.get(dt.datetime.combine(day.date, cls.start_time), 'local'),
            end=arrow.get(dt.datetime.combine(day.date, cls.end_time), 'local'),
            description=cls.description,
            location=cls.location
        ))

filename = inquirer.text("Calendar name")
with open(f'{filename}.ics', 'w') as f:
    f.writelines(calendar)
