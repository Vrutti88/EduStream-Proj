let currentCourseId = null;
let charts = {};

const NAV = {
  admin: [
    { id: 'overview', label: '📊 Overview' },
    { id: 'courses', label: '📚 Courses' },
    { id: 'attendance', label: '✅ Attendance' },
    { id: 'admin', label: '⚙️ Admin' },
    { id: 'notifications', label: '🔔 Notifications' },
  ],
  teacher: [
    { id: 'overview', label: '📊 Overview' },
    { id: 'courses', label: '📚 My Courses' },
    { id: 'attendance', label: '✅ Session Attendance' },
    { id: 'notifications', label: '🔔 Notifications' },
  ],
  student: [
    { id: 'overview', label: '📊 Overview' },
    { id: 'courses', label: '📚 Courses' },
    { id: 'attendance', label: '✅ My Attendance' },
    { id: 'notifications', label: '🔔 Notifications' },
  ],
};

function initDashboard() {
  if (!requireAuth()) return;
  const u = API.user;
  document.getElementById('user-greeting').textContent = `${u.name} · ${u.role}`;
  const nav = NAV[u.role] || NAV.student;
  const navHtml = nav.map(n =>
    `<a href="#" data-view="${n.id}"
        onclick="showView('${n.id}');return false">
        ${n.label}
     </a>`
  ).join('');
  
  if (API.user.role === 'admin') {
    document.getElementById('sidebar-nav').innerHTML =
      navHtml +
      `
      <hr style="margin:12px 0;border:none;border-top:1px solid var(--border)">
  
      <button
        class="btn small"
        style="width:100%;margin-top:8px"
        onclick="generateDemoData()">
  
        🎯 Generate Demo Data
  
      </button>
      `;
  } else {
    document.getElementById('sidebar-nav').innerHTML = navHtml;
  }

  if (u.role === 'student') document.getElementById('course-create-panel').classList.add('hidden');
  if (u.role !== 'admin') document.getElementById('overview-charts').classList.add('hidden');

  loadOverview();
  loadCourses();
  setInterval(refreshSessionButtons, 30000);
}

function showView(name) {
  document.querySelectorAll('.section-view').forEach(el => el.classList.remove('active'));
  document.getElementById(`view-${name}`)?.classList.add('active');
  document.querySelectorAll('.sidebar a').forEach(a => {
    a.classList.toggle('active', a.dataset.view === name);
  });
  if (name === 'attendance') loadAttendanceReport();
  if (name === 'admin') { loadAdminUsers(); loadAdminSessions(); }
  if (name === 'notifications') loadNotifications();
  if (name === 'courses') loadCourses();
}

async function loadOverview() {
  const role = API.user.role;
  try {
    if (role === 'admin') {
      const d = await API.request('/api/dashboard/admin');
      document.getElementById('overview-stats').innerHTML = [
        ['Users', d.stats.total_users], ['Teachers', d.stats.total_teachers],
        ['Students', d.stats.total_students], ['Courses', d.stats.total_courses],
        ['Sessions', d.stats.total_sessions], ['Live Now', d.stats.active_sessions],
      ].map(([l, n]) => `<div class="stat-card"><div class="num">${n}</div><div class="label">${l}</div></div>`).join('');
      renderChart('chart-enrollments', 'bar', d.enrollment_by_course.map(x => x.title), d.enrollment_by_course.map(x => x.count), 'Enrollments');
      renderChart('chart-sessions', 'doughnut', d.session_activity.map(x => x.status), d.session_activity.map(x => x.count));
    } else if (role === 'teacher') {
      const d = await API.request('/api/dashboard/teacher');
      document.getElementById('overview-stats').innerHTML = [
        ['My Courses', d.my_courses],

        ['My Sessions', d.my_sessions],

        ['Upcoming Sessions', d.upcoming_sessions_count],

        ['Students', d.student_count],

        // ['Attendance %',
        //   d.attendance_percentage || 0]
      ].map(([l, n]) => `<div class="stat-card"><div class="num">${n}</div><div class="label">${l}</div></div>`).join('');
      renderUpcoming(d.upcoming_sessions);
    } else {
      const d = await API.request('/api/dashboard/student');
      document.getElementById('overview-stats').innerHTML = `
        <div class="stat-card">
          <div class="num">${d.enrolled_courses}</div>
          <div class="label">Enrolled Courses</div>
        </div>

        <div class="stat-card">
          <div class="num">${d.attendance_percentage}%</div>
          <div class="label">Attendance %</div>
        </div>

        <div class="stat-card">
          <div class="num">${d.present_sessions || 0}</div>
          <div class="label">Present Sessions</div>
        </div>

        <div class="stat-card">
          <div class="num">${d.total_sessions || 0}</div>
          <div class="label">Total Sessions</div>
        </div>`
      // .map(([l,n]) =>
      //   `<div class="stat-card">
      //       <div class="num">${n}</div>
      //       <div class="label">${l}</div>
      //    </div>`
      // ).join('');
      renderUpcoming(d.upcoming_sessions);
      if (d.recent_announcements?.length) {
        document.getElementById('upcoming-panel').innerHTML = '<div class="panel-head"><h2>Recent Announcements</h2></div>' +
          d.recent_announcements.map(a => `<div style="padding:10px 0;border-bottom:1px solid var(--border)"><strong>${a.title}</strong><div class="meta">${a.course_title} · ${fmtTime(a.created_at)}</div><p style="font-size:.88rem;margin-top:4px">${a.content}</p></div>`).join('');
      }
    }
  } catch (e) { toast(e.message, true); }
}

function renderUpcoming(sessions) {
  const el = document.getElementById('upcoming-list');
  if (!sessions?.length) { el.innerHTML = '<div class="empty">No upcoming sessions</div>'; return; }
  el.innerHTML = `<table><thead><tr><th>Session</th><th>Course</th><th>Date</th><th>Status</th></tr></thead><tbody>${sessions.map(s => `<tr><td>${s.title}</td><td>${s.course_title || ''}</td><td>${s.session_date} ${s.start_time}</td><td>${badge(s.status || s.effective_status || 'scheduled')}</td></tr>`).join('')
    }</tbody></table>`;
}

function renderChart(id, type, labels, data, label = '') {
  const ctx = document.getElementById(id);
  if (!ctx) return;
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(ctx, {
    type,
    data: { labels, datasets: [{ label, data, backgroundColor: ['#5b8cff', '#7c5cff', '#34d399', '#fbbf24', '#f87171'] }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: getComputedStyle(document.body).color } } } }
  });
}

async function loadCourses() {
  const search = document.getElementById('course-search')?.value || '';
  const category = document.getElementById('course-filter')?.value || '';
  let url = '/api/courses?';
  if (search) url += `search=${encodeURIComponent(search)}&`;
  if (category) url += `category=${encodeURIComponent(category)}&`;
  const courses = await API.request(url);
  const cats = await API.request('/api/courses/categories').catch(() => []);
  const sel = document.getElementById('course-filter');
  if (sel && sel.options.length <= 1) cats.forEach(c => { const o = document.createElement('option'); o.value = c; o.textContent = c; sel.appendChild(o); });

  document.getElementById('course-grid').innerHTML = courses.length ? courses.map(c => `
    <div class="course-card">
      <h3>${c.title}</h3>
      <div class="meta">${c.course_code} · ${c.instructor_name || c.instructor || ''}</div>
      <p style="font-size:.85rem;color:var(--muted);flex:1">${c.description || ''}</p>
      <div><span class="meta-pill">${c.session_count || c.class_count || 0} sessions</span><span class="meta-pill">${c.enrolled_count || 0} enrolled</span></div>
      <div style="display:flex;gap:8px;margin-top:10px">
  <button class="btn ghost small" onclick="openCourse(${c.id})">
    Open →
  </button>

  ${(API.user.role === 'teacher' || API.user.role === 'admin') ? `
    <button class="btn small" onclick="editCourse(${c.id})">
      Edit
    </button>

    <button class="btn small danger" onclick="deleteCourse(${c.id})">
      Delete
    </button>
  ` : ''}
</div>
    </div>`).join('') : '<div class="empty">No courses found</div>';
}

async function createCourse() {
  try {
    await API.request('/api/courses', {
      method: 'POST', body: JSON.stringify({
        title: document.getElementById('c-title').value.trim(),
        course_code: document.getElementById('c-code').value.trim(),
        category: document.getElementById('c-category').value.trim(),
        description: document.getElementById('c-desc').value.trim(),
      })
    });
    toast('Course created');
    loadCourses();
  } catch (e) { toast(e.message, true); }
}

async function deleteCourse(courseId) {
  if (!confirm('Are you sure you want to delete this course?')) {
    return;
  }

  try {
    await API.request(`/api/courses/${courseId}`, {
      method: 'DELETE'
    });

    toast('Course deleted');
    loadCourses();

  } catch (e) {
    toast(e.message, true);
  }
}

async function editCourse(courseId) {

  const course = await API.request(`/api/courses/${courseId}`);

  const title = prompt('Course Title', course.title);

  if (!title) return;

  const description = prompt(
    'Course Description',
    course.description || ''
  );

  const category = prompt(
    'Category',
    course.category || ''
  );

  try {

    await API.request(`/api/courses/${courseId}`, {
      method: 'PUT',
      body: JSON.stringify({
        title,
        description,
        category
      })
    });

    toast('Course updated');

    loadCourses();

  } catch (e) {
    toast(e.message, true);
  }
}

async function openCourse(id) {
  currentCourseId = id;
  const c = await API.request(`/api/courses/${id}`);
  document.getElementById('detail-title').textContent = c.title;
  document.getElementById('detail-meta').textContent = `${c.course_code} · ${c.instructor_name} · ${c.category || 'General'}`;
  showView('course-detail');
  const role = API.user.role;
  document.getElementById('session-form').classList.toggle('hidden', role === 'student');
  document.getElementById('ann-form').classList.toggle('hidden', role === 'student');
  document.getElementById('schedule-session-btn')
    ?.classList.toggle(
      'hidden',
      role === 'student'
    );

  document.getElementById('announcement-btn')
    ?.classList.toggle(
      'hidden',
      role === 'student'
    );
  document.getElementById('mat-upload').classList.toggle('hidden', role === 'student');
  document.getElementById('enroll-form').classList.toggle('hidden', role !== 'student');
  loadSessions(); loadStudents(); loadAnnouncements(); loadMaterials();
}

async function loadSessions() {
  const sessions = await API.request(`/api/courses/${currentCourseId}/sessions`);
  const role = API.user.role;
  document.getElementById('session-list').innerHTML = sessions.map(s => {
    const st = s.effective_status || s.status;
    let actions = '';
    if (role === 'student') {
      actions = `<button class="btn small" ${s.can_join ? '' : 'disabled'} onclick="joinSession(${s.id})">${s.can_join ? 'Join' : 'Unavailable'}</button>`;
    } else if (role === 'teacher' || role === 'admin') {
      actions = `
<button class="btn ghost small" onclick="editSession(${s.id})">
  Edit
</button>

<button class="btn ghost small danger" onclick="deleteSession(${s.id})">
  Delete
</button>

<button class="btn ghost small" onclick="startSession(${s.id})">
  Start
</button>

<button class="btn ghost small" onclick="endSession(${s.id})">
  End
</button>

<button class="btn ghost small" onclick="cancelSession(${s.id})">
  Cancel
</button>
`;
    }
    return `<tr><td>${s.title}</td><td>${new Date(s.session_date).toLocaleDateString()}
    <br>
    ${s.start_time} - ${s.end_time}</td><td>${badge(st)}</td><td>${actions}</td></tr>`;
  }).join('') || '<tr><td colspan="4" class="empty">No sessions</td></tr>';
}

async function deleteSession(id) {

  if (!confirm('Delete this session?')) {
    return;
  }

  try {

    await API.request(`/api/sessions/${id}`, {
      method: 'DELETE'
    });

    toast('Session deleted');

    loadSessions();

  } catch (e) {

    toast(e.message, true);

  }
}

async function editSession(id) {

  try {

    const s =
      await API.request(`/api/sessions/${id}`);

    const title =
      prompt('Session Title', s.title);

    if (!title) return;

    const date =
      prompt(
        'Date (YYYY-MM-DD)',
        s.session_date
      );

    const start =
      prompt(
        'Start Time',
        s.start_time
      );

    const end =
      prompt(
        'End Time',
        s.end_time
      );

    await API.request(`/api/sessions/${id}`, {
      method: 'PUT',
      body: JSON.stringify({
        title,
        session_date: date,
        start_time: start,
        end_time: end
      })
    });

    toast('Session updated');

    loadSessions();

  } catch (e) {

    toast(e.message, true);

  }
}

async function createSession() {
  try {
    await API.request(`/api/courses/${currentCourseId}/sessions`, {
      method: 'POST', body: JSON.stringify({
        title: document.getElementById('s-title').value.trim(),
        session_date: document.getElementById('s-date').value,
        start_time: document.getElementById('s-start').value,
        end_time: document.getElementById('s-end').value,
        meeting_link: document.getElementById('s-link').value.trim(),
      })
    });
    toast('Session scheduled');
    loadSessions();
  } catch (e) { toast(e.message, true); }
}

async function joinSession(id) {
  try {

    const d = await API.request(
      `/api/sessions/${id}/join`,
      { method: 'POST', body: '{}' }
    );

    toast('Attendance marked successfully');

    if (d.meeting_link) {

      const openMeeting =
        confirm(
          `Attendance marked.\n\nOpen meeting link?\n\n${d.meeting_link}`
        );

      if (openMeeting) {
        window.open(d.meeting_link, '_blank');
      }
    }

    loadSessions();

  } catch (e) {

    toast(e.message, true);

  }
}

async function startSession(id) { await API.request(`/api/sessions/${id}/start`, { method: 'POST', body: '{}' }); loadSessions(); toast('Session started'); }
async function endSession(id) { await API.request(`/api/sessions/${id}/end`, { method: 'POST', body: '{}' }); loadSessions(); toast('Session ended'); }
async function cancelSession(id) { await API.request(`/api/sessions/${id}/cancel`, { method: 'POST', body: '{}' }); loadSessions(); toast('Session cancelled'); }

function refreshSessionButtons() {
  if (currentCourseId && document.getElementById('view-course-detail').classList.contains('active')) loadSessions();
}

async function loadStudents() {
  const students = await API.request(`/api/courses/${currentCourseId}/students`);
  document.getElementById('student-list').innerHTML = students.map(s =>
    `<tr><td>${s.student_name}</td><td>${s.student_email}</td><td>${fmtDate(s.enrolled_at)}</td></tr>`
  ).join('') || '<tr><td colspan="3" class="empty">No students</td></tr>';
}

async function enrollSelf() {
  try {
    await API.request(`/api/courses/${currentCourseId}/enroll`, { method: 'POST', body: '{}' });
    toast('Enrolled successfully');
    loadStudents();
  } catch (e) { toast(e.message, true); }
}

async function loadAnnouncements() {
  const items = await API.request(`/api/courses/${currentCourseId}/announcements`);
  document.getElementById('ann-list').innerHTML = items.map(a =>
    `<div style="padding:10px 0;border-bottom:1px solid var(--border)"><strong>${a.title}</strong> <span class="meta">${fmtTime(a.created_at)}</span><p style="font-size:.88rem;margin-top:4px">${a.content}</p></div>`
  ).join('') || '<div class="empty">No announcements</div>';
}

async function postAnnouncement() {
  try {
    await API.request(`/api/courses/${currentCourseId}/announcements`, {
      method: 'POST', body: JSON.stringify({
        title: document.getElementById('a-title').value.trim(),
        content: document.getElementById('a-content').value.trim(),
      })
    });
    toast('Announcement posted');
    loadAnnouncements();
  } catch (e) { toast(e.message, true); }
}

async function loadMaterials() {
  const items = await API.request(`/api/courses/${currentCourseId}/materials`);
  document.getElementById('mat-list').innerHTML = items.map(m =>
    `<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border)">
      <span>${m.original_name} <span class="meta-pill">${m.file_type}</span></span>
      <a href="/api/materials/${m.id}/download" class="btn ghost small" style="text-decoration:none">Download</a>
    </div>`
  ).join('') || '<div class="empty">No materials</div>';
}

async function uploadMaterial() {
  const file = document.getElementById('mat-file').files[0];
  if (!file) return toast('Select a file', true);
  const fd = new FormData();
  fd.append('file', file);
  try {
    const headers = {};
    if (API.token) headers['Authorization'] = `Bearer ${API.token}`;
    const res = await fetch(`/api/courses/${currentCourseId}/materials`, { method: 'POST', headers, body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Upload failed');
    toast('Material uploaded');
    loadMaterials();
  } catch (e) { toast(e.message, true); }
}

async function loadAttendanceReport() {

  const role = API.user.role;

  if (role === 'student') {

    document.querySelector('#view-attendance thead tr').innerHTML = `
    <th>Course</th>
    <th>Session</th>
    <th>Date</th>
    <th>Join Time</th>
    <th>Status</th>
`;

    const rows =
      await API.request('/api/my/attendance');

    document.getElementById(
      'attendance-report'
    ).innerHTML =
      rows.map(r => `
        <tr>
          <td>${r.course_title}</td>
          <td>${r.session_title}</td>
          <td>${r.session_date}</td>
          <td>${fmtTime(r.join_time)}</td>
          <td>${badge(r.status)}</td>
        </tr>
      `).join('') ||
      '<tr><td colspan="5">No attendance records</td></tr>';

    return;
  }

  document.querySelector('#view-attendance thead tr').innerHTML = `
    <th>Course</th>
    <th>Session</th>
    <th>Date</th>
    <th>Present</th>
    <th>Enrolled</th>
    <th>Action</th>
`;

  const rows =
    await API.request('/api/attendance/reports');
    console.log("Attendance Rows:", rows);

  document.getElementById(
    'attendance-report'
  ).innerHTML =
    rows.map(r => `
      <tr>
        <td>${r.course_title}</td>
        <td>${r.session_title}</td>
        <td>${r.session_date}</td>
        <td>${r.present_count}</td>
        <td>${r.enrolled_count}</td>
        <td>
          <button
            class="btn small"
            onclick="viewAttendanceDetails(${r.session_id})">
            View
          </button>
        </td>
      </tr>
    `).join('') ||
    '<tr><td colspan="6">No data</td></tr>';
}

async function loadAdminUsers() {
  const users = await API.request('/api/admin/users');
  document.getElementById('admin-users').innerHTML = users.map(u =>
    `<tr><td>${u.name}</td><td>${u.email}</td><td>${badge(u.role)}</td><td><button class="btn ghost small danger" onclick="deleteUser(${u.id})">Delete</button></td></tr>`
  ).join('');
}

async function deleteUser(id) {
  if (!confirm('Delete this user?')) return;
  try { await API.request(`/api/admin/users/${id}`, { method: 'DELETE' }); loadAdminUsers(); toast('User deleted'); }
  catch (e) { toast(e.message, true); }
}

async function loadAdminSessions() {
  const sessions = await API.request('/api/admin/sessions');
  document.getElementById('admin-sessions').innerHTML = sessions.map(s =>
    `<tr><td>${s.title}</td><td>${s.course_title}</td><td>${badge(s.status)}</td><td>${s.instructor_name}</td></tr>`
  ).join('');
}

async function loadNotifications() {
  const items = await API.request('/api/notifications');
  document.getElementById('notif-list').innerHTML = items.map(n =>
    `<div style="padding:12px 0;border-bottom:1px solid var(--border);opacity:${n.is_read ? '.6' : '1'}">
      <strong>${n.title}</strong> <span class="meta-pill">${n.type}</span>
      <p style="font-size:.88rem;margin-top:4px">${n.message}</p>
      <span class="meta">${fmtTime(n.created_at)}</span>
    </div>`
  ).join('') || '<div class="empty">No notifications</div>';
}

async function markAllRead() {
  await API.request('/api/notifications/read-all', { method: 'POST', body: '{}' });
  loadNotifications();
  toast('All marked as read');
}

async function viewAttendanceDetails(sessionId) {

  try {

    const rows = await API.request(
      `/api/sessions/${sessionId}/attendance-details`
    );

    document
      .getElementById(
        'attendance-details-body'
      )
      .innerHTML =
      rows.map(r => `
              <tr>
                  <td>${r.name}</td>
                  <td>${r.email}</td>

                  <td>
                      ${r.status === 'Present'
          ? '🟢 Present'
          : '🔴 Absent'
        }
                  </td>
              </tr>
          `).join('');

    document
      .getElementById(
        'attendance-modal'
      )
      .classList.remove('hidden');

  }
  catch (e) {
    toast(e.message, true);
  }
}

function closeAttendanceModal() {

  document
    .getElementById(
      'attendance-modal'
    )
    .classList.add('hidden');
}

async function generateDemoData() {

  if (!confirm('Generate demo data?')) {
    return;
  }

  try {

    const res = await API.request(
      '/api/demo/seed',
      {
        method: 'POST',
        body: '{}'
      }
    );

    toast(
      res.message ||
      'Demo data generated successfully'
    );

    loadOverview();
    loadCourses();

  } catch (e) {

    toast(e.message, true);

  }
}

initDashboard();
