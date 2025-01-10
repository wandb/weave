sqlite3 cereal.db

> .mode csv
> .separator ;
> .import cereal.csv cereal

> .read sqlite_cereal.sql
> drop table _cereal_old;
