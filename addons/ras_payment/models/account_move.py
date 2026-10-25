from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    ras_amount_tva = fields.Monetary(
        string="Montant RAS TVA",
        compute='_compute_ras_amount',
        currency_field='currency_id',
        store=True,
    )

    ras_amount_is = fields.Monetary(
        string="Montant RAS IS",
        compute='_compute_ras_amount',
        currency_field='currency_id',
        store=True,
    )

    ras_amount_ir = fields.Monetary(
        string="Montant RAS IR",
        compute='_compute_ras_amount',
        currency_field='currency_id',
        store=True,
    )

    ras_amount_export = fields.Monetary(
        string="Montant RAS Non-résident",
        compute='_compute_ras_amount',
        currency_field='currency_id',
        store=True,
    )

    ras_amount = fields.Monetary(
        string="Montant RAS Total",
        compute='_compute_ras_amount',
        currency_field='currency_id',
        store=True,
    )

    @api.depends(
        'invoice_line_ids.ras_amount',
        'invoice_line_ids.ras_amount_tva',
        'invoice_line_ids.ras_amount_is',
        'invoice_line_ids.ras_amount_ir',
        'invoice_line_ids.ras_amount_export',
    )
    def _compute_ras_amount(self):

        for move in self:

            move.ras_amount_tva = sum(
                move.invoice_line_ids.mapped(
                    'ras_amount_tva'
                )
            )

            move.ras_amount_is = sum(
                move.invoice_line_ids.mapped(
                    'ras_amount_is'
                )
            )

            move.ras_amount_ir = sum(
                move.invoice_line_ids.mapped(
                    'ras_amount_ir'
                )
            )

            move.ras_amount_export = sum(
                move.invoice_line_ids.mapped(
                    'ras_amount_export'
                )
            )

            move.ras_amount = (
                move.ras_amount_tva
                + move.ras_amount_is
                + move.ras_amount_ir
                + move.ras_amount_export
            )


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    ras_amount_tva = fields.Monetary(
        string="Montant RAS TVA",
        currency_field='currency_id',
        readonly=True,
        copy=False,
    )

    ras_amount_is = fields.Monetary(
        string="Montant RAS IS",
        currency_field='currency_id',
        readonly=True,
        copy=False,
    )

    ras_amount_ir = fields.Monetary(
        string="Montant RAS IR",
        currency_field='currency_id',
        readonly=True,
        copy=False,
    )

    ras_amount_export = fields.Monetary(
        string="Montant RAS Non-résident",
        currency_field='currency_id',
        readonly=True,
        copy=False,
    )

    ras_amount = fields.Monetary(
        string="Montant RAS Total",
        currency_field='currency_id',
        readonly=True,
        copy=False,
    )

    visuel_tax_ids = fields.Many2many(
        'account.tax',
        'account_move_line_visuel_tax_rel',
        'line_id',
        'tax_id',
        string="Taxes",
        domain=[
            ('ras_is_retenue_source', '=', False)
        ],
    )

    @api.onchange('visuel_tax_ids')
    def _onchange_visuel_tax_ids(self):

        for line in self:
            line.tax_ids = line.visuel_tax_ids

    @api.model_create_multi
    def create(self, vals_list):

        lines = super().create(vals_list)

        for line in lines:

            if not line.visuel_tax_ids and line.tax_ids:

                taxes_normales = line.tax_ids.filtered(
                    lambda t: not t.ras_is_retenue_source
                )

                line.visuel_tax_ids = [
                    (6, 0, taxes_normales.ids)
                ]

        return lines