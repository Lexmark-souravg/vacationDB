SELECT a.`first_name`, a.`last_name`, ac.`empl_num`, ac.`department_number`
FROM auth_user a, accounts_profile ac, vacationdb_vacationallotment v, vacationdb_vacationschedule vs
WHERE ac.`user_id` = a.`id` AND a.`id` AND v.`user_id` AND v.`schedule_id`=vs.`id` AND vs.`id` = ?