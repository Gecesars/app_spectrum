Coloque aqui os CSVs paramétricos das normas. Nomes esperados pelo loader:

- normas_fm_classes.csv (classe,erp_max_kw,hnmt_max_m,dist_max_contorno66_km)
- normas_fm_protecao.csv (tipo_interferencia,delta_f_khz,ci_requerida_db)
- normas_fm_radcom_distancias.csv (classe_fm,situacao,dist_min_km)
- normas_radcom.csv (erp_max_w,raio_servico_km,altura_max_m)
- normas_tv_digital_classes.csv (classe,faixa_canal,erp_max_kw,hnmt_ref_m,dist_max_contorno_protegido_km)
- normas_tv_analogica_classes.csv (classe,faixa_canal,erp_max_kw,hnmt_ref_m,dist_max_contorno_protegido_km)
- normas_tv_protecao.csv (tipo_interferencia,tecnologia_desejado,tecnologia_interferente,delta_canal,ci_requerida_db,observacao)
- normas_tv_fm_compatibilidade.csv (canal_tv,faixa_canais_fm,tipo_interferencia,ci_requerida_db)
- normas_tv_nivel_contorno.csv (tecnologia,faixa_canal,nivel_campo_dbuv_m)

Se algum arquivo não existir, o loader apenas ignora. Para RadCom, se não houver CSV, ele insere um valor padrão (25 W, raio 1 km, altura 30 m) conforme codex.
